from backend.main import app

SCHEMA = app.openapi()


def operations():
    for path, methods in SCHEMA["paths"].items():
        for method, operation in methods.items():
            yield f"{method.upper()} {path}", operation


def body_schema(operation):
    content = operation["requestBody"]["content"]["application/json"]["schema"]
    return SCHEMA["components"]["schemas"][content["$ref"].split("/")[-1]]


def test_every_operation_has_an_id_and_a_one_line_docstring():
    for name, operation in operations():
        assert operation.get("operationId"), name
        assert operation.get("description"), name
        assert "\n" not in operation["description"], name


def test_no_operation_has_an_optional_input():
    for name, operation in operations():
        for parameter in operation.get("parameters", []):
            assert parameter["required"], f"{name} {parameter['name']}"
        if "requestBody" in operation:
            assert operation["requestBody"]["required"], name
            schema = body_schema(operation)
            assert set(schema.get("required", [])) == set(schema["properties"]), name
