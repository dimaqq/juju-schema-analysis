import json


def python_type(js: str):
    return {"string": "str",
            "number": "float",
            "integer": "int",
            "boolean": "bool",
            "object": "dict[Any, Any]"}[js]

def pattern_name(p: str):
    return {".*": '"abc"'}.get(p, p)


def linearise(schema, defs, path="", done=None):
    if done is None:
        done = set()

    if (ref := schema.get("$ref")):
        assert ref.startswith("#/definitions/")

        ref_name = ref.split("#/definitions/", 1)[1]
        yield f"{path}: {ref_name}"

        if ref_name in done:
            return

        done.add(ref_name)
        assert ref_name in defs

        ref_schema = defs[ref_name]
        yield from linearise(ref_schema, defs, path, done.copy())
        return

    assert (type_ := schema.get("type"))
    if type_ == "object":
        if (props := schema.get("properties")):
            for prop_name, sch in props.items():
                yield from linearise(sch, defs, f"{path}.{prop_name}", done.copy())

        elif (props := schema.get("patternProperties")):
            for pattern, sch in props.items():
                yield from linearise(sch, defs, f"{path}[{pattern_name(pattern)}]", done.copy())

        else:
            yield f"{path}: {python_type(type_)}"

    elif type_ == "array":
        assert (sch := schema.get("items"))
        yield from linearise(sch, defs, f"{path}[0]", done.copy())

    else:
        yield f"{path}: {python_type(type_)}"
    

def parse_definitions(defs: dict) -> dict[str, str]:
    return {n: "\n".join(linearise(v, defs)) for n, v in defs.items()}


def main(data: list, *, api_group: str):
    for facade in data:
        if api_group not in facade["AvailableTo"]:
            continue

        defs = facade["Schema"].get("definitions") or {}
        for method, body in facade["Schema"]["properties"].items():
            try:
                params = body["properties"]["Params"]
            except KeyError:
                args = ": None"
            else:
                args = "\n".join(linearise(params, defs))

            try:
                result = body["properties"]["Result"]
            except KeyError:
                rets = ": None"
            else:
                rets = "\n".join(linearise(result, defs))

            yield f"{facade['Name']}: {facade['Version']}"
            yield f".{method}()"
            yield f"in{args}"
            yield f"out{rets}"
            yield ""


if __name__ == "__main__":
    from pathlib import Path
    for inp in Path(".").glob("schemas-juju-*.json"):
        schemata = json.loads(inp.read_text())
        inp.with_suffix(".model-user.txt").write_text("\n".join(main(schemata, api_group="model-user")))
        inp.with_suffix(".controller-user.txt").write_text("\n".join(main(schemata, api_group="controller-user")))


def test_main():
    schema_str = '''
    {
        "definitions": {
            "DeleteSecretArg": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string"
                    },
                    "revisions": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        }
                    },
                    "uri": {
                        "type": "string"
                    }
                },
                "additionalProperties": false,
                "required": [
                    "uri",
                    "label"
                ]
            },
            "DeleteSecretArgs": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "array",
                        "items": {
                            "$ref": "#/definitions/DeleteSecretArg"
                        }
                    }
                },
                "additionalProperties": false,
                "required": [
                    "args"
                ]
            },
            "Error": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string"
                    },
                    "info": {
                        "type": "object",
                        "patternProperties": {
                            ".*": {
                                "type": "object",
                                "additionalProperties": true
                            }
                        }
                    },
                    "message": {
                        "type": "string"
                    }
                },
                "additionalProperties": false,
                "required": [
                    "message",
                    "code"
                ]
            }
        }
    }
    '''
    schema = json.loads(schema_str)
    definitions = schema.get('definitions', {})
    for def_name, def_schema in definitions.items():
        print(f"# {def_name}")
        for n in linearise(def_schema, definitions):
            print(n)
        print()

