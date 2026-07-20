"""Register legacy cases with one explicit feature/responsibility owner."""


def register_cases(owner, method_names):
    for method_name in method_names:
        legacy_name = "_case_" + method_name[5:]
        setattr(owner, method_name, getattr(owner, legacy_name))
