from itertools import chain
from pathlib import Path

import pandas as pd
import yaml


def format_edges(edges):
    """Format edges dictionary into readable markdown."""
    if not edges or not isinstance(edges, dict):
        return ""

    parts = []
    if edges.get("to"):
        parts.append(f"**To:**<br> {'<br> '.join(edges['to'])}")
    if edges.get("from"):
        parts.append(f"**From:**<br> {'<br> '.join(edges['from'])}")

    return "<br>".join(parts) if parts else ""


def format_list(entry):
    if not entry or not isinstance(entry, list):
        return entry

    return "<br> ".join(entry)


def format_dict(entry) -> str:
    if not entry or not isinstance(entry, dict):
        return entry

    result: str = ""
    for k,v in entry.items():
        desc = v

        if isinstance(v, list):
            desc = "<br> ".join(v)

        result += f"**{k}**:<br> {desc}<br>"

    return result.replace("- >", "").replace("\n", "<br>")


def collapse_column(entry):

    if isinstance(entry, str):
        return entry.replace("- >", "").replace("\n", "<br>")
    elif isinstance(entry, list) and len(entry) == 1:
        return entry[0].replace("- >", "").replace("\n", "<br>")
    elif not isinstance(entry, list):
        return entry

    flattened_list = list(chain.from_iterable(item if isinstance(item, list) else [item] for item in entry))
    full_desc = "<br> ".join(flattened_list).replace("- >", "").replace("\n", "<br>")

    return full_desc


def yaml_to_markdown_table(yaml_file, ytype):
    with open(yaml_file, "r") as f:
        data = yaml.safe_load(f)

    collapsable = ["description", "shortDescription", "longDescription", "examples"]

    # Convert to DataFrame
    df = pd.DataFrame(data.get(ytype))

    for col in df.columns:
        if col in collapsable:
            df[col] = df[col].apply(collapse_column)
        elif col == "edges":
            df[col] = df[col].apply(format_edges)
        elif col == "tourContent":
            df[col] = df[col].apply(format_dict)
        else:
            df[col] = df[col].apply(format_list)

    df_filled = df.fillna("").sort_values("id")

    # Convert to markdown
    return df_filled.to_markdown(index=False)


# Components
in_file = Path("./risk-map/yaml/components.yaml")
out_file = Path("./out.md")
# Usage
result = yaml_to_markdown_table(yaml_file=in_file, ytype="components")

with open(out_file, mode="w") as of:
    of.write(result)

# Controls
in_file = Path("./risk-map/yaml/controls.yaml")
out_file = Path("out-controls.md")
result = yaml_to_markdown_table(yaml_file=in_file, ytype="controls")

with open(out_file, mode="w") as of:
    of.write(result)

# Risks
in_file = Path("./risk-map/yaml/risks.yaml")
out_file = Path("out-risks.md")
result = yaml_to_markdown_table(yaml_file=in_file, ytype="risks")

with open(out_file, mode="w") as of:
    of.write(result)
