from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ContainerWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (
            ROOT / ".github" / "workflows" / "container-image.yml"
        ).read_text(encoding="utf-8")

    def test_only_main_and_stable_release_jobs_publish(self):
        self.assertIn("pull_request:", self.workflow)
        self.assertIn("branches:\n      - main", self.workflow)
        self.assertIn("release:\n    types:\n      - published", self.workflow)
        self.assertIn("github.event.release.prerelease == false", self.workflow)
        self.assertIn("push: false", self.workflow)
        self.assertEqual(1, self.workflow.count("push: true"))

    def test_publish_job_has_scoped_package_permission(self):
        top_level = self.workflow.split("jobs:", 1)[0]
        self.assertIn("permissions:\n  contents: read", top_level)
        self.assertNotIn("packages: write", top_level)
        publish = self.workflow.split("  publish:", 1)[1]
        self.assertIn("contents: read", publish)
        self.assertIn("packages: write", publish)
        self.assertIn("persist-credentials: false", publish)

    def test_publication_uses_expected_registry_and_tags(self):
        for contract in (
            "IMAGE_NAME: ghcr.io/tzu-huang/healthcare-lab",
            "type=raw,value=edge",
            "type=sha,prefix=sha-",
            "type=semver,pattern={{version}}",
            "type=semver,pattern={{major}}.{{minor}}",
            "type=semver,pattern={{major}}",
            "type=raw,value=latest",
        ):
            self.assertIn(contract, self.workflow)
        self.assertIn("Verify anonymous GHCR access", self.workflow)
        self.assertIn("docker logout ghcr.io", self.workflow)
        self.assertIn("docker buildx imagetools inspect", self.workflow)
        self.assertNotIn("gh api --method PATCH", self.workflow)

    def test_release_contract_is_validated_before_registry_mutation(self):
        self.assertIn("Validate stable release contract", self.workflow)
        self.assertIn('=~ ^v?[0-9]+\\.[0-9]+\\.[0-9]+$', self.workflow)
        self.assertIn("REPOSITORY_VISIBILITY", self.workflow)
        self.assertIn('!= "public"', self.workflow)
        self.assertLess(
            self.workflow.index("Validate stable release contract"),
            self.workflow.index("Log in to GitHub Container Registry"),
        )
        self.assertIn("Verify public GHCR package before stable mutation", self.workflow)
        self.assertIn('imagetools inspect "${IMAGE_NAME}:edge"', self.workflow)
        self.assertIn("set the package visibility to Public in GitHub", self.workflow)
        self.assertLess(
            self.workflow.index("Verify public GHCR package before stable mutation"),
            self.workflow.index("Log in to GitHub Container Registry"),
        )

    def test_release_build_uses_release_ref_and_is_idempotent(self):
        self.assertIn("github.event.release.tag_name || github.sha", self.workflow)
        self.assertIn("Guard immutable release version", self.workflow)
        self.assertIn('docker pull "${IMAGE_NAME}:${VERSION}"', self.workflow)
        self.assertIn("org.opencontainers.image.revision", self.workflow)
        self.assertIn('"${EXISTING_REVISION}" != "${GITHUB_SHA}"', self.workflow)
        self.assertIn('echo "reuse_release=true"', self.workflow)
        self.assertIn("steps.release_guard.outputs.reuse_release != 'true'", self.workflow)
        self.assertIn('VERSION="${RELEASE_TAG#v}"', self.workflow)

    def test_same_commit_rerun_repairs_every_release_alias(self):
        self.assertIn("Repair release aliases from immutable image", self.workflow)
        self.assertIn("docker buildx imagetools create", self.workflow)
        self.assertIn('"${IMAGE_NAME}:${VERSION}"', self.workflow)
        for alias in (
            '"${IMAGE_NAME}:${MAJOR}.${MINOR}"',
            '"${IMAGE_NAME}:${MAJOR}"',
            '"${IMAGE_NAME}:latest"',
            '"${IMAGE_NAME}:sha-${SHORT_SHA}"',
        ):
            self.assertIn(f"--tag {alias}", self.workflow)
        self.assertIn(
            'for TAG in "${VERSION}" "${MAJOR}.${MINOR}" "${MAJOR}" latest "sha-${SHORT_SHA}"',
            self.workflow,
        )

    def test_required_verification_precedes_publication(self):
        self.assertIn("needs: verify", self.workflow)
        self.assertIn("python -m unittest discover -s tests", self.workflow)
        self.assertIn("platforms: linux/amd64", self.workflow)
        self.assertIn("docker/build-push-action@v7", self.workflow)


if __name__ == "__main__":
    unittest.main()
