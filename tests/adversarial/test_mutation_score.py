from __future__ import annotations

import ast
import copy
from pathlib import Path
import types
from typing import Any, Callable, Dict, List, Tuple

import agy_codex_studio.contracts as contracts_mod

SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "agy_codex_studio"


def _load_mutated_module(module_name: str, tree: ast.Module, filename: Path) -> types.ModuleType:
    ast.fix_missing_locations(tree)
    code = compile(tree, str(filename), "exec")
    mod = types.ModuleType(f"agy_codex_studio._mutant_{module_name}")
    mod.__package__ = "agy_codex_studio"
    mod.__file__ = str(filename)
    # Pre-bind package sibling contracts for relative import `from .contracts import ...`
    exec(code, mod.__dict__)
    return mod


def _collect_function_mutation_sites(
    source: str, target_functions: set[str]
) -> List[Tuple[str, int, str, Callable[[ast.AST], None]]]:
    """Discover deterministic comparison, boolean, and arithmetic AST mutation sites inside core functions."""
    base_tree = ast.parse(source)
    sites: List[Tuple[str, int, str, Callable[[ast.AST], None]]] = []

    cmp_swaps: Dict[type[ast.cmpop], Callable[[], ast.cmpop]] = {
        ast.Lt: ast.GtE,
        ast.LtE: ast.Gt,
        ast.Gt: ast.LtE,
        ast.GtE: ast.Lt,
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
    }
    bin_swaps: Dict[type[ast.operator], Callable[[], ast.operator]] = {
        ast.Add: ast.Sub,
        ast.Sub: ast.Add,
        ast.Mult: ast.Div,
    }
    bool_swaps: Dict[type[ast.boolop], Callable[[], ast.boolop]] = {
        ast.And: ast.Or,
        ast.Or: ast.And,
    }

    for top_node in base_tree.body:
        if not isinstance(top_node, ast.FunctionDef) or top_node.name not in target_functions:
            continue
        fn_name = top_node.name
        subnodes = list(ast.walk(top_node))
        for node_idx, node in enumerate(subnodes):
            if isinstance(node, ast.Compare) and len(node.ops) == 1:
                op_type = type(node.ops[0])
                if op_type in cmp_swaps:
                    swap_cls = cmp_swaps[op_type]

                    def make_cmp_mutator(f_name: str, idx: int, cls: Callable[[], ast.cmpop]) -> Callable[[ast.AST], None]:
                        def _mutate(root: ast.AST) -> None:
                            fn = next(
                                n for n in root.body  # type: ignore[attr-defined]
                                if isinstance(n, ast.FunctionDef) and n.name == f_name
                            )
                            target = list(ast.walk(fn))[idx]
                            assert isinstance(target, ast.Compare)
                            target.ops[0] = cls()

                        return _mutate

                    sites.append((fn_name, getattr(node, "lineno", 0), f"cmp:{op_type.__name__}", make_cmp_mutator(fn_name, node_idx, swap_cls)))

            elif isinstance(node, ast.BinOp) and type(node.op) in bin_swaps:
                op_type = type(node.op)
                swap_cls_b = bin_swaps[op_type]

                def make_bin_mutator(f_name: str, idx: int, cls: Callable[[], ast.operator]) -> Callable[[ast.AST], None]:
                    def _mutate(root: ast.AST) -> None:
                        fn = next(
                            n for n in root.body  # type: ignore[attr-defined]
                            if isinstance(n, ast.FunctionDef) and n.name == f_name
                        )
                        target = list(ast.walk(fn))[idx]
                        assert isinstance(target, ast.BinOp)
                        target.op = cls()

                    return _mutate

                sites.append((fn_name, getattr(node, "lineno", 0), f"bin:{op_type.__name__}", make_bin_mutator(fn_name, node_idx, swap_cls_b)))

            elif isinstance(node, ast.BoolOp) and type(node.op) in bool_swaps:
                op_type = type(node.op)
                swap_cls_bool = bool_swaps[op_type]

                def make_bool_mutator(f_name: str, idx: int, cls: Callable[[], ast.boolop]) -> Callable[[ast.AST], None]:
                    def _mutate(root: ast.AST) -> None:
                        fn = next(
                            n for n in root.body  # type: ignore[attr-defined]
                            if isinstance(n, ast.FunctionDef) and n.name == f_name
                        )
                        target = list(ast.walk(fn))[idx]
                        assert isinstance(target, ast.BoolOp)
                        target.op = cls()

                    return _mutate

                sites.append((fn_name, getattr(node, "lineno", 0), f"bool:{op_type.__name__}", make_bool_mutator(fn_name, node_idx, swap_cls_bool)))

    return sites


def _oracle_caption_engine(mod: Any) -> None:
    WT = contracts_mod.WordTimestamp
    CG = contracts_mod.CaptionGroup

    assert mod._format_srt_time(3661.5) == "01:01:01,500"
    assert mod._format_vtt_time(3661.5) == "01:01:01.500"
    assert mod.sanitize_cue_text("a\n\nb --> c", escape_vtt_arrows=False) == "a\nb -> c"
    assert mod.sanitize_cue_text("a\n\nb --> c", escape_vtt_arrows=True) == "a\nb --&gt; c"
    assert mod.sanitize_cue_text("   \n  ", escape_vtt_arrows=False) == ""

    try:
        mod.build_caption_groups([WT("x", 0.0, 0.5)], max_words=0)
        raise AssertionError("Expected max_words=0 to raise")
    except ValueError:
        pass
    assert len(mod.build_caption_groups([WT("x", 0.0, 0.5)], max_words=1, pause_break_sec=0.0)) == 1

    try:
        mod.build_caption_groups([WT("x", 0.0, 0.5)], max_words=2, pause_break_sec=-0.01)
        raise AssertionError("Expected negative pause_break_sec to raise")
    except ValueError:
        pass

    assert mod.build_caption_groups([]) == []
    words = [
        WT("  ", 0.0, 0.1),
        WT("Hello,", 0.1, 0.3),
        WT("world", 0.35, 0.6),
        WT("now", 0.62, 0.8),
        WT("afterPause", 1.5, 1.9),
    ]
    groups = mod.build_caption_groups(words, max_words=4, pause_break_sec=0.4)
    assert [g.text for g in groups] == ["Hello,", "world now", "afterPause"]
    assert groups[0].start == 0.1 and groups[0].end == 0.3
    max2_groups = mod.build_caption_groups(
        [WT("one", 0.0, 0.2), WT("two", 0.22, 0.4), WT("three", 0.42, 0.6)],
        max_words=2,
        pause_break_sec=0.5,
    )
    assert [g.text for g in max2_groups] == ["one two", "three"]

    assert mod.format_srt_document([]) == ""
    assert mod.format_vtt_document([]) == "WEBVTT\n"
    inv = CG(id="c1", text="line1\n\n00:00:01,000 --> 00:00:02,000", start=2.0, end=1.0, words=[WT("w", 2.0, 2.0)])
    srt = mod.format_srt_document([inv])
    vtt = mod.format_vtt_document([inv])
    assert "00:00:02,000 --> 00:00:02,000" in srt
    assert "00:00:02.000 --> 00:00:02.000" in vtt
    assert srt.count(" --> ") == 1
    assert vtt.count(" --> ") == 1

    payload = mod.build_captions_payload(groups)
    assert payload["meta"]["group_count"] == 3
    assert payload["meta"]["start_sec"] == 0.1
    assert payload["meta"]["end_sec"] == 1.9
    assert payload["captions"][0]["startMs"] == 100
    assert payload["captions"][0]["endMs"] == 300


def _oracle_ghost_trimmer(mod: Any) -> None:
    WT = contracts_mod.WordTimestamp
    CI = contracts_mod.CutInterval

    assert mod._clean_token("  Um... ") == "um"
    merged = mod._merge_cut_intervals(
        [CI(1.0, 2.0, "a"), CI(2.0, 1.5, "empty"), CI(2.00005, 3.0, "b"), CI(4.0, 4.5, "c")]
    )
    assert len(merged) == 2
    assert abs(merged[0].start - 1.0) < 1e-6 and abs(merged[0].end - 3.0) < 1e-6
    assert merged[0].reason == "a;b"
    assert abs(mod._remap_point(2.5, merged) - 1.0) < 1e-6
    assert abs(mod._remap_point(3.5, merged) - 1.5) < 1e-6

    empty_res = mod.detect_and_trim_words([], max_pause_sec=0.0, pad_start_sec=0.0, pad_end_sec=0.0)
    assert empty_res["saved_seconds"] == 0.0

    try:
        mod.detect_and_trim_words([WT("bad", float("nan"), 1.0)])
        raise AssertionError("Expected NaN start to raise")
    except ValueError:
        pass

    # Exact arithmetic verification for lead_silence, inter-word silence, pad_start, pad_end, and remapped durations
    exact_two = mod.detect_and_trim_words(
        [WT("first", 1.0, 1.5), WT("second", 3.5, 4.0)],
        max_pause_sec=0.5,
        pad_start_sec=0.1,
        pad_end_sec=0.2,
    )
    assert exact_two["saved_seconds"] == 2.6
    assert [(round(c.start, 3), round(c.end, 3), c.reason) for c in exact_two["cut_intervals"]] == [
        (0.0, 0.9, "lead_silence"),
        (1.7, 3.4, "silence"),
    ]
    assert [(w.start, w.end) for w in exact_two["remapped_words"]] == [(0.1, 0.6), (0.9, 1.4)]

    # Tight speech below max_pause_sec produces zero cuts (verifies > max_pause and cut_end > cut_start)
    no_cut = mod.detect_and_trim_words(
        [WT("immediate", 0.1, 0.4), WT("close", 0.95, 1.2)],
        max_pause_sec=0.5,
        pad_start_sec=0.35,
        pad_end_sec=0.35,
    )
    assert no_cut["cut_intervals"] == []
    assert no_cut["saved_seconds"] == 0.0

    for bad_kwargs in (
        {"max_pause_sec": -0.1},
        {"pad_start_sec": -0.1},
        {"pad_end_sec": -0.1},
    ):
        try:
            mod.detect_and_trim_words([WT("a", 0.0, 0.2)], **bad_kwargs)
            raise AssertionError("Expected negative param to raise")
        except ValueError:
            pass

    # Lead silence + retake within 8s vs >8s + filler + inter-word silence + punctuation non-retake
    stream = [
        WT("...", 1.0, 1.1),
        WT("Signal", 1.12, 1.35),
        WT("?!", 1.38, 1.42),
        WT("Signal", 1.45, 1.65),
        WT("STM32", 1.70, 1.95),
        WT("locks", 1.98, 2.20),
        WT("um", 2.25, 2.45),
        WT("STM32", 2.50, 2.75),
        WT("locks", 2.78, 3.05),
        WT("uh", 3.10, 3.30),
        WT("cleanly", 4.50, 4.90),
        WT("STM32", 12.00, 12.30),  # > 8.0s away, must NOT retake-prune earlier "STM32 locks"
        WT("locks", 12.32, 12.60),
    ]
    out = mod.detect_and_trim_words(stream, max_pause_sec=0.5, pad_start_sec=0.04, pad_end_sec=0.05)
    kept_texts = [w.word for w in out["kept_words"]]
    assert kept_texts.count("Signal") == 2
    assert kept_texts.count("STM32") == 2
    assert out["removed_fillers"] == 1
    assert any("lead_silence" in c.reason for c in out["cut_intervals"])
    assert any("retake" in c.reason for c in out["cut_intervals"])
    assert any("silence" in c.reason for c in out["cut_intervals"])
    remapped = out["remapped_words"]
    for i in range(len(remapped) - 1):
        assert remapped[i].start < remapped[i].end <= remapped[i + 1].start + 1e-6


def _oracle_shorts_scorer(mod: Any) -> None:
    TS = contracts_mod.TranscriptSegment

    assert mod._score_hook("") == 2.0
    h_strong = mod._score_hook("99.5% STM32 4000 Hz corrupts raw signal?")
    h_dangling = mod._score_hook("and plain words")
    assert h_strong == 10.0
    assert h_dangling == 2.0

    assert mod._score_coherence("", "", "") == 2.0
    c_bad_open = mod._score_coherence("so it drifted,", "so it drifted", "so it drifted,")
    c_good = mod._score_coherence(
        '"STM32 captures eight clean engineered telemetry words today."',
        '"STM32 captures eight clean"',
        'engineered telemetry words today."',
    )
    assert c_bad_open == 0.0
    assert c_good == 10.0

    e_high = mod._score_emotion_and_proof("Verified zero drops deterministic corrupts captures")
    e_tok_only = mod._score_emotion_and_proof("verified")
    e_phrase_only = mod._score_emotion_and_proof("achieves zero drops today")
    e_low = mod._score_emotion_and_proof("nothing special here")
    assert e_high == 10.0
    assert e_tok_only == 5.0
    assert e_phrase_only == 7.5
    assert e_low == 2.0

    assert mod._score_density("hello plain words", 5.0) == 1.0
    assert abs(mod._score_density("crc--32", 10.0) - 2.8) < 1e-6
    d_short_dur = mod._score_density("STM32", 0.2)
    d_long_dur = mod._score_density("STM32", 10.0)
    assert d_short_dur == 10.0
    assert abs(d_long_dur - 2.8) < 1e-6

    segs_tight = [TS(0, "A", 0.0, 5.0), TS(1, "B", 5.05, 10.0), TS(2, "C", 10.05, 15.0)]
    segs_wide = [TS(0, "A", 0.0, 5.0), TS(1, "B", 5.20, 10.0), TS(2, "C", 10.20, 15.0)]
    assert mod._score_boundaries(segs_tight, 0, 2) == 10.0
    assert mod._score_boundaries(segs_tight, 1, 1) == 5.0
    assert mod._score_boundaries(segs_wide, 1, 1) == 10.0

    assert mod.score_transcript_segments([]) == []
    try:
        mod.score_transcript_segments([TS(1, "A.", float("nan"), 10.0)])
        raise AssertionError("Expected NaN segment start to raise")
    except ValueError:
        pass
    try:
        mod.score_transcript_segments([TS(1, "A.", 0.0, 10.0)], target_min_sec=20.0, target_max_sec=10.0)
        raise AssertionError("Expected target_max < target_min to raise")
    except ValueError:
        pass
    try:
        mod.score_transcript_segments([TS(1, "A.", 0.0, 10.0)], target_min_sec=0.0, target_max_sec=10.0)
        raise AssertionError("Expected target_min <= 0 to raise")
    except ValueError:
        pass

    segs = [
        TS(1, "STM32 captures 4000 Hz DMA with 99.5% CRC-32 verified.", 100.0, 110.0),
        TS(2, "and plain filler text,", 110.05, 122.0),
        TS(3, "Trailing extra long segment.", 122.05, 150.0),
    ]
    res = mod.score_transcript_segments(segs, target_min_sec=10.0, target_max_sec=25.0)
    assert len(res) >= 2
    assert all(10.0 <= (c.end - c.start) <= 25.0 for c in res)
    assert res[0].score > res[-1].score

    # Fallback candidate when no sub-window matches [target_min_sec, target_max_sec]
    fallback = mod.score_transcript_segments([TS(1, "Short clip.", 1.0, 4.0)], target_min_sec=15.0, target_max_sec=30.0)
    assert len(fallback) == 1
    assert fallback[0].natural_boundaries == 8.0


def test_ast_mutation_kill_score_exceeds_95_percent() -> None:
    targets = [
        (
            "caption_engine",
            SRC_DIR / "caption_engine.py",
            {"sanitize_cue_text", "_normalized_bounds", "build_caption_groups", "format_srt_document", "format_vtt_document"},
            _oracle_caption_engine,
        ),
        (
            "ghost_trimmer",
            SRC_DIR / "ghost_trimmer.py",
            {"_merge_cut_intervals", "_remap_point", "detect_and_trim_words"},
            _oracle_ghost_trimmer,
        ),
        (
            "shorts_scorer",
            SRC_DIR / "shorts_scorer.py",
            {"_score_hook", "_score_coherence", "_score_emotion_and_proof", "_score_density", "_score_boundaries", "score_transcript_segments"},
            _oracle_shorts_scorer,
        ),
    ]

    total_mutants = 0
    killed_mutants = 0
    survivors: List[str] = []

    for mod_name, file_path, fn_names, oracle_fn in targets:
        source = file_path.read_text(encoding="utf-8")
        base_tree = ast.parse(source)
        # Sanity check: unmutated module must pass oracle 100%
        clean_mod = _load_mutated_module(mod_name, copy.deepcopy(base_tree), file_path)
        oracle_fn(clean_mod)

        sites = _collect_function_mutation_sites(source, fn_names)
        # Sample deterministically up to 25 rich AST sites per module (75 total mutants) for fast CI execution
        selected_sites = sites[:25]
        for fn_name, lineno, desc, mutator in selected_sites:
            total_mutants += 1
            mut_tree = copy.deepcopy(base_tree)
            mutator(mut_tree)
            try:
                mut_mod = _load_mutated_module(mod_name, mut_tree, file_path)
                oracle_fn(mut_mod)
                survivors.append(f"{mod_name}.{fn_name}:L{lineno} ({desc})")
            except Exception:
                killed_mutants += 1

    assert total_mutants >= 50
    kill_score = killed_mutants / total_mutants
    print(f"\n[AST Mutation Audit] {killed_mutants}/{total_mutants} killed ({kill_score:.2%})")
    assert kill_score >= 0.95, (
        f"Mutation kill score {kill_score:.2%} ({killed_mutants}/{total_mutants}) < 95%; "
        f"survivors={survivors}"
    )
