from sigrity_mcp.core import results


def test_classify_output_touchstone():
    assert results.classify_output("out.s2p") == "touchstone"
    assert results.classify_output("out.s4p") == "touchstone"
    assert results.classify_output("out.s10p") == "touchstone"


def test_classify_output_other_kinds():
    assert results.classify_output("report.log") == "text_report"
    assert results.classify_output("data.csv") == "csv"
    assert results.classify_output("model.sp") == "spice_netlist"
    assert results.classify_output("design.spd") == "sigrity_design"
    assert results.classify_output("weird.xyz") == "xyz"
    assert results.classify_output("noext") == "unknown"


def test_touchstone_summary_parses_header(tmp_path):
    path = tmp_path / "out.s2p"
    path.write_text(
        "! comment line\n"
        "# GHz S MA R 50\n"
        "1.0 0.5 -10 0.01 90 0.01 90 0.5 -10\n"
        "2.0 0.4 -20 0.02 80 0.02 80 0.4 -20\n",
        encoding="utf-8",
    )
    summary = results.touchstone_summary(path)
    assert summary["port_count"] == 2
    assert summary["option_line"] == "# GHz S MA R 50"
    assert summary["data_line_count"] == 2
    assert summary["size_bytes"] > 0


def test_text_preview_head_and_tail(tmp_path):
    path = tmp_path / "report.log"
    lines = [f"line {i}" for i in range(100)]
    path.write_text("\n".join(lines), encoding="utf-8")

    preview = results.text_preview(path, max_lines=10)
    assert preview["total_lines"] == 100
    assert preview["head"] == [f"line {i}" for i in range(5)]
    assert preview["tail"] == [f"line {i}" for i in range(95, 100)]


def test_text_preview_short_file_has_no_duplicate_tail(tmp_path):
    path = tmp_path / "short.log"
    path.write_text("a\nb\nc", encoding="utf-8")
    preview = results.text_preview(path, max_lines=80)
    assert preview["total_lines"] == 3
    assert preview["tail"] == []
