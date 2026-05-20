import pandas as pd
import zipfile

from src.data_mapping import create_best_mapping_preview, create_mapping_preview
from src.loader import load_data
from src.llm_mapper import generate_column_mapping
from src.scorer import score_creatives


def test_create_mapping_preview_reports_validation_and_sample_rows():
    df = pd.DataFrame(
        {
            "Creative Concept": ["Pixel Pro Video"],
            "Where it ran": ["TikTok"],
            "The Objective": ["Video Views"],
            "Total Spent": [1500],
            "Impressions Total": [100000],
            "People Reached": [80000],
            "Link Clicks": [500],
            "3s Video Plays": [20000],
            "100% Video Completions": [1000],
            "Buying Method": ["Paid"],
            "Format Type": ["Video"],
            "Planner Notes": ["keep this out"],
        }
    )

    preview = create_mapping_preview(
        df,
        sheet_name="Planner Export",
        mapping={
            "Creative Concept": "creative_name",
            "Where it ran": "platform",
            "The Objective": "objective",
            "Total Spent": "spend",
            "Impressions Total": "impressions",
            "People Reached": "reach",
            "Link Clicks": "clicks",
            "3s Video Plays": "vtr_2s",
            "100% Video Completions": "video_views_100",
            "Buying Method": "buying_type",
            "Format Type": "format_raw",
        },
    )

    assert preview["sheet_name"] == "Planner Export"
    assert preview["proposed_mapping"]["Creative Concept"] == "creative_name"
    assert preview["missing_required_fields"] == []
    assert preview["ignored_columns"] == ["Planner Notes"]
    assert preview["sample_normalized_rows"][0]["creative_name"] == "Pixel Pro Video"
    assert preview["sample_normalized_rows"][0]["platform"] == "TikTok"
    assert preview["confidence_by_field"]["creative_name"] >= 0.8


def test_create_mapping_preview_handles_duplicate_source_columns():
    df = pd.DataFrame(
        [
            ["Creative A", "Meta", "Awareness", 1000, 999, 30000, 20000],
            ["Creative B", "TikTok", "Video Views", 1200, 888, 40000, 25000],
        ],
        columns=[
            "Creative Name",
            "Platform",
            "Objective",
            "Spends",
            "Spends",
            "Impressions",
            "Reach",
        ],
    )

    preview = create_mapping_preview(
        df,
        "Data Analysis (All)",
        {
            "Creative Name": "creative_name",
            "Platform": "platform",
            "Objective": "objective",
            "Spends": "spend",
            "Impressions": "impressions",
            "Reach": "reach",
        },
    )

    assert preview["ready_to_ingest"] is True
    assert preview["sample_normalized_rows"][0]["spend"] == 1000
    spend_diagnostic = next(
        item for item in preview["mapping_diagnostics"] if item["canonical_field"] == "spend"
    )
    assert spend_diagnostic["sample_values"] == ["1000", "1200"]


def test_create_mapping_preview_separates_metadata_from_ignored_columns():
    df = pd.DataFrame(
        {
            "creative_name": ["Pixel Pro Video"],
            "platform": ["TikTok"],
            "objective": ["Video Views"],
            "spend": [1500],
            "impressions": [100000],
            "video_views_100": [1000],
            "concept": ["Creator Demo"],
            "Planner Notes": ["keep this out"],
        }
    )

    preview = create_mapping_preview(
        df,
        sheet_name="Canonical Export",
        mapping={
            "creative_name": "creative_name",
            "platform": "platform",
            "objective": "objective",
            "spend": "spend",
            "impressions": "impressions",
        },
    )

    assert preview["proposed_mapping"]["video_views_100"] == "video_views_100"
    assert preview["proposed_mapping"]["concept"] == "concept"
    assert "video_views_100" in preview["canonical_mapped_fields"]
    assert "concept" in preview["preserved_metadata_fields"]
    assert preview["ignored_columns"] == ["Planner Notes"]
    assert preview["sample_normalized_rows"][0]["video_views_100"] == 1000
    assert preview["sample_normalized_rows"][0]["concept"] == "Creator Demo"


def test_load_data_uses_explicit_mapping_for_unstructured_csv(tmp_path):
    csv_path = tmp_path / "planner_export.csv"
    pd.DataFrame(
        {
            "Creative Concept": ["Pixel Pro Video", "Pixel Static"],
            "Where it ran": ["TikTok", "Meta"],
            "The Objective": ["Video Views", "Awareness"],
            "Total Spent": [1500, 900],
            "Impressions Total": [100000, 50000],
            "People Reached": [80000, 45000],
            "Link Clicks": [500, 100],
            "3s Video Plays": [20000, 0],
            "100% Video Completions": [1000, 0],
            "Buying Method": ["Paid", "Paid"],
            "Format Type": ["Video", "Static"],
            "Campaign Concept": ["Creator Demo", "Brand Still"],
        }
    ).to_csv(csv_path, index=False)

    mapping = {
        "Creative Concept": "creative_name",
        "Where it ran": "platform",
        "The Objective": "objective",
        "Total Spent": "spend",
        "Impressions Total": "impressions",
        "People Reached": "reach",
        "Link Clicks": "clicks",
        "3s Video Plays": "vtr_2s",
        "100% Video Completions": "video_views_100",
        "Buying Method": "buying_type",
        "Format Type": "format_raw",
        "Campaign Concept": "concept",
    }

    df_raw, df = load_data(str(csv_path), column_mapping=mapping)

    assert len(df_raw) == 2
    assert set(df_raw["platform"]) == {"Meta", "TikTok"}
    assert set(df["creative_name"]) == {"Pixel Pro Video", "Pixel Static"}
    assert set(df["concept"]) == {"Creator Demo", "Brand Still"}
    assert df["spend"].sum() == 2400


def test_load_data_preserves_explicit_custom_metadata_columns(tmp_path):
    csv_path = tmp_path / "planner_export.csv"
    pd.DataFrame(
        {
            "Creative Concept": ["Pixel Pro Video", "Pixel Static"],
            "Where it ran": ["TikTok", "Meta"],
            "The Objective": ["Video Views", "Awareness"],
            "Total Spent": [1500, 900],
            "Impressions Total": [100000, 50000],
            "Review Owner": ["Ana", "Max"],
        }
    ).to_csv(csv_path, index=False)

    mapping = {
        "Creative Concept": "creative_name",
        "Where it ran": "platform",
        "The Objective": "objective",
        "Total Spent": "spend",
        "Impressions Total": "impressions",
    }

    df_raw, df = load_data(
        str(csv_path),
        column_mapping=mapping,
        preserve_columns=["Review Owner"],
    )

    assert "metadata_review_owner" in df_raw.columns
    assert "metadata_review_owner" in df.columns
    assert set(df["metadata_review_owner"]) == {"Ana", "Max"}


def test_mapping_preview_warns_when_video_id_is_scientific_notation():
    df = pd.DataFrame(
        {
            "Ad name": [
                "(OPID-4624155)_Pixel_YouTube_20s_Generic_Vertical_GStore_Imp"
            ],
            "Video ID": ["3.25846E+11"],
            "Platform": ["YouTube"],
            "Objective": ["Video Views"],
            "Cost": [80.8],
            "Impr.": ["8,189"],
        }
    )

    preview = create_mapping_preview(
        df,
        "Updated Creative Report Template",
        {
            "Ad name": "creative_name",
            "Video ID": "video_id",
            "Platform": "platform",
            "Objective": "objective",
            "Cost": "spend",
            "Impr.": "impressions",
        },
    )

    assert preview["proposed_mapping"]["Ad name"] == "creative_name"
    assert preview["proposed_mapping"]["Video ID"] == "video_id"
    assert "video_id" in preview["preserved_metadata_fields"]
    assert any("scientific notation" in warning for warning in preview["warnings"])


def test_load_data_uses_ad_name_key_and_extracts_opid_when_video_id_is_unsafe(tmp_path):
    csv_path = tmp_path / "youtube_mid_funnel.csv"
    ad_name = "(OPID-4624155)_Pixel_YouTube_20s_Generic_Vertical_GStore_Imp"
    pd.DataFrame(
        {
            "Ad name": [ad_name],
            "Video ID": ["3.25846E+11"],
            "Platform": ["YouTube"],
            "Objective": ["Video Views"],
            "Cost": ["80.8"],
            "Impr.": ["8,189"],
            "Clicks": [7],
        }
    ).to_csv(csv_path, index=False)

    df_raw, df = load_data(
        str(csv_path),
        column_mapping={
            "Ad name": "creative_name",
            "Video ID": "video_id",
            "Platform": "platform",
            "Objective": "objective",
            "Cost": "spend",
            "Impr.": "impressions",
            "Clicks": "clicks",
        },
    )

    assert df_raw["creative_name"].iloc[0] == ad_name
    assert df_raw["ad_name_raw"].iloc[0] == ad_name
    assert df_raw["ad_id"].iloc[0] == "OPID-4624155"
    assert df_raw["video_id"].iloc[0] == "3.25846E+11"
    assert df["creative_name"].iloc[0] == ad_name
    assert df["ad_id"].iloc[0] == "OPID-4624155"
    assert df["video_id"].iloc[0] == "3.25846E+11"


def test_youtube_mid_funnel_preview_derives_platform_and_objective_without_manual_columns(tmp_path):
    csv_path = tmp_path / "youtube_mid_funnel.csv"
    pd.DataFrame(
        {
            "Campaign": [
                "1713870 | Pixel | BR | ESS01 | EMEA | GB | en | Hybrid | YT | COMBO | YT TF | GAds_Arm 1"
            ],
            "Ad type": ["Responsive video ad"],
            "Video ID": ["3.25846E+11"],
            "Ad name": [
                "(OPID-4624155)_Flame_GB_YouTube_Video_YouTube_Hyb_HYB_None_In-stream-video_Q1_TF-3.0-Arm-1_Deep-Thoughts_20s_Generic_Vertical_GStore_Imp"
            ],
            "Impr.": ["8,189"],
            "Clicks": ["7"],
            "Cost": ["80.8"],
            "TrueView views": ["0"],
            "TrueView view rate": ["0"],
            "Engagements": ["0"],
            "Engagement rate": ["0.00%"],
            "Video played to 25%": ["96.16%"],
            "Video played to 50%": ["91.98%"],
            "Video played to 75%": ["90.03%"],
            "Video played to 100%": ["88.88%"],
        }
    ).to_csv(csv_path, index=False)

    preview = create_best_mapping_preview(str(csv_path))

    assert preview["ready_to_ingest"] is True
    assert preview["derived_fields"]["platform"]["value"] == "YouTube"
    assert preview["derived_fields"]["objective"]["value"] == "Target Frequency"
    assert preview["proposed_mapping"]["Ad name"] == "creative_name"
    assert preview["proposed_mapping"]["TrueView views"] == "trueview_views"
    assert preview["proposed_mapping"]["Video played to 100%"] == "video_quartile_p100_rate"
    assert "platform" not in preview["missing_required_fields"]
    assert "objective" not in preview["missing_required_fields"]
    assert any("scientific notation" in warning for warning in preview["warnings"])


def test_load_data_derives_youtube_context_and_trueview_eligibility(tmp_path):
    csv_path = tmp_path / "youtube_mid_funnel.csv"
    ad_name = "(OPID-4624155)_Flame_GB_YouTube_Video_YouTube_Hyb_HYB_None_In-stream-video_Q1_TF-3.0-Arm-1_Deep-Thoughts_20s_Generic_Vertical_GStore_Imp"
    pd.DataFrame(
        {
            "Campaign": [
                "1713870 | Pixel | BR | ESS01 | EMEA | GB | en | Hybrid | YT | COMBO | YT TF | GAds_Arm 1",
                "1713870 | Pixel | BR | ESS01 | EMEA | GB | en | Hybrid | YT | COMBO | YT TF | GAds_Arm 1",
            ],
            "Ad type": ["Responsive video ad", "Responsive video ad"],
            "Video ID": ["3.25846E+11", "3.25846E+11"],
            "Ad name": [ad_name, ad_name],
            "Impr.": ["8,189", "18,978"],
            "Clicks": ["7", "38"],
            "Cost": ["800.00", "1,218.64"],
            "TrueView views": ["0", "1,756"],
            "TrueView view rate": ["0", "23.44%"],
            "Engagements": ["0", "2,813"],
            "Engagement rate": ["0.00%", "14.82%"],
            "Video played to 25%": ["96.16%", "88.24%"],
            "Video played to 50%": ["91.98%", "65.22%"],
            "Video played to 75%": ["90.03%", "60.07%"],
            "Video played to 100%": ["88.88%", "57.17%"],
        }
    ).to_csv(csv_path, index=False)

    df_raw, df = load_data(str(csv_path))

    assert set(df_raw["platform"]) == {"YouTube"}
    assert set(df_raw["objective"]) == {"Target Frequency"}
    assert set(df_raw["platform_source"]) == {"derived"}
    assert set(df_raw["objective_source"]) == {"derived"}
    assert df_raw["ad_id"].iloc[0] == "OPID-4624155"
    assert df_raw["video_id"].iloc[0] == "3.25846E+11"
    assert df_raw["trueview_eligible"].tolist() == [False, True]
    assert df_raw["youtube_measurement_family"].tolist() == [
        "completion_only",
        "trueview_eligible",
    ]
    assert round(df_raw["completion_rate"].iloc[0], 2) == 88.88
    assert round(df_raw["trueview_view_rate"].iloc[1], 2) == 23.44
    assert df["duration_s"].iloc[0] == 20
    assert bool(df["low_confidence"].iloc[0]) is False
    assert bool(df["trueview_eligible"].iloc[0]) is True
    assert df["youtube_measurement_family"].iloc[0] == "mixed"
    assert round(df["video_quartile_p100_rate"].iloc[0], 2) == 66.73
    assert "Target Frequency | YouTube" in df["objective"].iloc[0] + " | " + df["platform"].iloc[0]

    scored = score_creatives(df)
    assert scored["scoring_group"].iloc[0].endswith("| mixed")


def test_heuristic_mapping_handles_planner_export_labels(monkeypatch):
    def fail_llm(*args, **kwargs):
        raise RuntimeError("force heuristic fallback")

    df = pd.DataFrame(
        {
            "Creative Concept": ["Pixel Pro Video"],
            "Where it ran": ["TikTok"],
            "The Objective": ["Video Views"],
            "Total Spent": [1500],
            "Impressions Total": [100000],
            "People Reached": [80000],
            "Link Clicks": [500],
            "3s Video Plays": [20000],
            "100% Video Completions": [1000],
            "Total Engagements": [3200],
        }
    )
    monkeypatch.setattr("src.llm_mapper.genai.Client", fail_llm)

    mapping = generate_column_mapping(df)

    assert mapping["Creative Concept"] == "creative_name"
    assert mapping["Where it ran"] == "platform"
    assert mapping["The Objective"] == "objective"
    assert mapping["Total Spent"] == "spend"
    assert mapping["Impressions Total"] == "impressions"
    assert mapping["People Reached"] == "reach"
    assert mapping["Link Clicks"] == "clicks"
    assert mapping["3s Video Plays"] == "vtr_2s"
    assert mapping["100% Video Completions"] == "video_views_100"
    assert mapping["Total Engagements"] == "engagements"


def test_load_data_uses_explicit_sheet_name_header_row_and_performance_score(tmp_path):
    workbook_path = tmp_path / "full_workbook_shape.xlsx"
    df = pd.DataFrame(
        {
            "Creative Name": ["Creative A", "Creative B"],
            "Platform": ["Meta", "Meta"],
            "Objective": ["Awareness", "Awareness"],
            "Format": ["Video", "Video"],
            "Placement": ["Feed", "Feed"],
            "Campaign": ["Campaign 1", "Campaign 1"],
            "Reach": [20000, 25000],
            "Impressions": [30000, 40000],
            "Spends": [1000, 1200],
            "3s VTR": [10.0, 20.0],
            "Video Completion": [300, 800],
            "Total Engagement": [100, 300],
            "Creative Efficiency Index": [44.0, 91.0],
            "Concept": ["Concept A", "Concept B"],
        }
    )
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            sheet_name="Data Analysis (All)",
            startrow=5,
            index=False,
        )

    df_raw, df_agg = load_data(
        str(workbook_path),
        sheet_name="Data Analysis (All)",
        header_row=6,
    )

    assert len(df_raw) == 2
    assert set(df_agg["creative_name"]) == {"Creative A", "Creative B"}
    assert "performance_score" in df_agg.columns
    assert df_agg.loc[df_agg["creative_name"] == "Creative B", "performance_score"].iloc[0] == 91.0


def _write_bad_dimension_workbook(path, df):
    original = path.with_name("original.xlsx")
    with pd.ExcelWriter(original, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            sheet_name="Data Analysis (All)",
            startrow=5,
            index=False,
        )
    with zipfile.ZipFile(original, "r") as zin, zipfile.ZipFile(path, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(b'<dimension ref="A1:O9"/>', b'<dimension ref="A1:A1"/>')
                data = data.replace(b'<dimension ref="A1:N9"/>', b'<dimension ref="A1:A1"/>')
            zout.writestr(item, data)


def test_preview_auto_detects_xlsx_header_from_xml_when_pandas_empty(monkeypatch, tmp_path):
    workbook_path = tmp_path / "bad_dimension.xlsx"
    df = pd.DataFrame(
        {
            "Creative Name": ["Creative A"],
            "Platform": ["Meta"],
            "Objective": ["Awareness"],
            "Spends": [1000],
            "Impressions": [30000],
            "Reach": [20000],
        }
    )
    _write_bad_dimension_workbook(workbook_path, df)

    monkeypatch.setattr("src.data_mapping.pd.read_excel", lambda *args, **kwargs: pd.DataFrame())

    preview = create_best_mapping_preview(
        str(workbook_path),
        sheet_name="Data Analysis (All)",
        mapping_provider=lambda frame: {
            "Creative Name": "creative_name",
            "Platform": "platform",
            "Objective": "objective",
            "Spends": "spend",
            "Impressions": "impressions",
            "Reach": "reach",
        },
    )

    assert preview["ready_to_ingest"] is True
    assert preview["source_columns"][:5] == [
        "Creative Name",
        "Platform",
        "Objective",
        "Spends",
        "Impressions",
    ]
    assert preview["detected_header_row"] == 6


def test_preview_standard_aliases_do_not_require_llm(monkeypatch, tmp_path):
    workbook_path = tmp_path / "standard_aliases.xlsx"
    df = pd.DataFrame(
        {
            "Creative Name": ["Creative A"],
            "Platform": ["Meta"],
            "Objective": ["Awareness"],
            "Spends": [1000],
            "Impressions": [30000],
            "Reach": [20000],
            "Creative Efficiency Index": [88.0],
            "Concept": ["Concept A"],
        }
    )
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            sheet_name="Data Analysis (All)",
            startrow=5,
            index=False,
        )

    def fail_if_called(_):
        raise AssertionError("LLM mapper should not be called for standard aliases")

    monkeypatch.setattr("src.llm_mapper.generate_column_mapping", fail_if_called)

    preview = create_best_mapping_preview(
        str(workbook_path),
        sheet_name="Data Analysis (All)",
    )

    assert preview["ready_to_ingest"] is True
    assert preview["proposed_mapping"]["Creative Name"] == "creative_name"
    assert preview["proposed_mapping"]["Spends"] == "spend"
    assert preview["proposed_mapping"]["Creative Efficiency Index"] == "performance_score"


def test_preview_auto_header_xlsx_does_not_call_pandas_read_excel(monkeypatch, tmp_path):
    workbook_path = tmp_path / "standard_aliases.xlsx"
    df = pd.DataFrame(
        {
            "Creative Name": ["Creative A"],
            "Platform": ["Meta"],
            "Objective": ["Awareness"],
            "Spends": [1000],
            "Impressions": [30000],
            "Reach": [20000],
        }
    )
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data Analysis (All)", startrow=5, index=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("selected auto-header xlsx should use XML reader first")

    monkeypatch.setattr("src.data_mapping.pd.read_excel", fail_if_called)

    preview = create_best_mapping_preview(
        str(workbook_path),
        sheet_name="Data Analysis (All)",
    )

    assert preview["ready_to_ingest"] is True
    assert preview["detected_header_row"] == 6


def test_load_data_auto_detects_xlsx_header_from_xml_when_pandas_empty(monkeypatch, tmp_path):
    workbook_path = tmp_path / "bad_dimension.xlsx"
    df = pd.DataFrame(
        {
            "Creative Name": ["Creative A", "Creative B"],
            "Platform": ["Meta", "TikTok"],
            "Objective": ["Awareness", "Video Views"],
            "Format": ["Video", "Video"],
            "Placement": ["Feed", "In Feed"],
            "Campaign": ["Campaign 1", "Campaign 2"],
            "Reach": [20000, 25000],
            "Impressions": [30000, 40000],
            "Spends": [1000, 1200],
            "Creative Efficiency Index": [44.0, 91.0],
            "Concept": ["Concept A", "Concept B"],
        }
    )
    _write_bad_dimension_workbook(workbook_path, df)

    monkeypatch.setattr("src.loader.pd.read_excel", lambda *args, **kwargs: pd.DataFrame())

    df_raw, df_agg = load_data(
        str(workbook_path),
        sheet_name="Data Analysis (All)",
    )

    assert len(df_raw) == 2
    assert set(df_agg["creative_name"]) == {"Creative A", "Creative B"}
    assert df_agg.loc[df_agg["creative_name"] == "Creative B", "performance_score"].iloc[0] == 91.0


def test_load_data_auto_header_xlsx_does_not_call_pandas_read_excel(monkeypatch, tmp_path):
    workbook_path = tmp_path / "standard_aliases.xlsx"
    df = pd.DataFrame(
        {
            "Creative Name": ["Creative A", "Creative B"],
            "Platform": ["Meta", "TikTok"],
            "Objective": ["Awareness", "Video Views"],
            "Format": ["Video", "Video"],
            "Placement": ["Feed", "In Feed"],
            "Campaign": ["Campaign 1", "Campaign 2"],
            "Reach": [20000, 25000],
            "Impressions": [30000, 40000],
            "Spends": [1000, 1200],
            "Creative Efficiency Index": [44.0, 91.0],
        }
    )
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data Analysis (All)", startrow=5, index=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("selected auto-header xlsx should use XML reader first")

    monkeypatch.setattr("src.loader.pd.read_excel", fail_if_called)

    df_raw, df_agg = load_data(
        str(workbook_path),
        sheet_name="Data Analysis (All)",
    )

    assert len(df_raw) == 2
    assert set(df_agg["creative_name"]) == {"Creative A", "Creative B"}
