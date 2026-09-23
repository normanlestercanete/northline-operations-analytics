"""Apply the edited Operations Overview layout to the other report pages.

Run after editing Operations Overview in Power BI Desktop. Visual queries and
page-specific formatting remain on their original pages.
"""

import copy
import hashlib
import json
from pathlib import Path


REPORT = Path(__file__).resolve().parents[1] / "Northline.Report" / "report.json"


def visual_type(visual):
    return json.loads(visual["config"])["singleVisual"]["visualType"]


def position(visual):
    return json.loads(visual["config"])["layouts"][0]["position"]


def move_like(visual, template):
    config = json.loads(visual["config"])
    template_position = position(template)
    config["layouts"][0]["position"] = copy.deepcopy(template_position)
    visual["config"] = json.dumps(config, separators=(",", ":"), ensure_ascii=False)
    for key in ("x", "y", "width", "height", "z"):
        visual[key] = round(template_position[key], 2)


def field(visual):
    config = json.loads(visual["config"])
    projections = config["singleVisual"].get("projections", {})
    return next(
        (item["queryRef"] for group in projections.values() for item in group if "queryRef" in item),
        None,
    )


def is_heading(visual):
    return visual_type(visual) == "cardVisual" and field(visual) == "Metrics.Report Heading"


def is_footer(visual):
    return visual_type(visual) == "textbox" and position(visual)["y"] > 1000


def is_title(visual):
    return visual_type(visual) == "textbox" and not is_footer(visual)


def table_alignment(visual, template):
    config = json.loads(visual["config"])
    template_config = json.loads(template["config"])
    example = template_config["singleVisual"]["objects"]["columnFormatting"][0]
    numeric_fields = [
        item["queryRef"]
        for group in config["singleVisual"]["projections"].values()
        for item in group
        if item.get("queryRef", "").startswith("Metrics.")
    ]
    config["singleVisual"].setdefault("objects", {})["columnFormatting"] = [
        {"properties": copy.deepcopy(example["properties"]), "selector": {"metadata": name}}
        for name in numeric_fields
    ]
    visual["config"] = json.dumps(config, separators=(",", ":"), ensure_ascii=False)


def main():
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    overview = next(section for section in report["sections"] if section["displayName"] == "Operations Overview")
    types = {}
    for visual in overview["visualContainers"]:
        types.setdefault(visual_type(visual), []).append(visual)

    title_template = next(visual for visual in types["textbox"] if is_title(visual))
    heading_template = next(visual for visual in types["cardVisual"] if is_heading(visual))
    logo_template = types["image"][0]
    cards = sorted((visual for visual in types["cardVisual"] if not is_heading(visual)), key=lambda v: position(v)["x"])
    slicers = sorted(types["slicer"], key=lambda v: position(v)["y"])
    charts = sorted(
        (visual for visual in overview["visualContainers"] if visual_type(visual) not in ("image", "textbox", "cardVisual", "slicer")),
        key=lambda v: (position(v)["y"], position(v)["x"]),
    )
    assert len(cards) == 6 and len(slicers) == 4 and len(charts) == 4
    table_template = next(visual for visual in charts if visual_type(visual) == "tableEx")

    for section in report["sections"]:
        if section is overview:
            continue
        section["config"] = overview["config"]
        visuals = section["visualContainers"]
        old_titles = [visual for visual in visuals if is_title(visual)]
        assert len(old_titles) in (1, 3), section["displayName"]
        title = next(visual for visual in old_titles if position(visual)["x"] > 300)
        title_text = json.loads(title["config"])["singleVisual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]["value"]
        title_config = json.loads(title["config"])
        template_config = json.loads(title_template["config"])
        title_config["singleVisual"] = copy.deepcopy(template_config["singleVisual"])
        title_config["singleVisual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]["value"] = title_text
        title["config"] = json.dumps(title_config, separators=(",", ":"), ensure_ascii=False)
        move_like(title, title_template)
        visuals[:] = [visual for visual in visuals if visual not in old_titles or visual is title]

        heading = next(visual for visual in visuals if is_heading(visual))
        heading_config = json.loads(heading["config"])
        heading_config["singleVisual"]["objects"] = copy.deepcopy(json.loads(heading_template["config"])["singleVisual"]["objects"])
        heading_config["singleVisual"]["vcObjects"] = copy.deepcopy(json.loads(heading_template["config"])["singleVisual"]["vcObjects"])
        heading["config"] = json.dumps(heading_config, separators=(",", ":"), ensure_ascii=False)
        move_like(heading, heading_template)

        page_cards = sorted((visual for visual in visuals if visual_type(visual) == "cardVisual" and not is_heading(visual)), key=lambda v: position(v)["x"])
        assert len(page_cards) == 6, section["displayName"]
        for visual, template in zip(page_cards, cards):
            move_like(visual, template)

        page_slicers = sorted(
            (visual for visual in visuals if visual_type(visual) == "slicer"),
            key=lambda v: (position(v)["x"], position(v)["y"]),
        )
        assert 3 <= len(page_slicers) <= 4, section["displayName"]
        for visual, template in zip(page_slicers, slicers):
            move_like(visual, template)

        page_charts = sorted(
            (visual for visual in visuals if visual_type(visual) not in ("image", "textbox", "cardVisual", "slicer")),
            key=lambda v: (position(v)["y"], position(v)["x"]),
        )
        assert len(page_charts) == 4, section["displayName"]
        for visual, template in zip(page_charts, charts):
            move_like(visual, template)
        table_alignment(next(visual for visual in page_charts if visual_type(visual) == "tableEx"), table_template)

        visuals[:] = [visual for visual in visuals if visual_type(visual) != "image"]
        logo = copy.deepcopy(logo_template)
        logo_config = json.loads(logo["config"])
        logo_config["name"] = hashlib.sha1(section["name"].encode()).hexdigest()[:20]
        logo["config"] = json.dumps(logo_config, separators=(",", ":"), ensure_ascii=False)
        visuals.append(logo)

    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
