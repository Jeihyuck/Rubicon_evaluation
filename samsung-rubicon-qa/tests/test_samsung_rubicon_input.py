"""Tests for input candidate scoring and failure classification."""

from __future__ import annotations

from app.samsung_rubicon import _classify_input_candidate_metadata, _score_input_candidate_metadata


class TestInputCandidateScoring:
    def test_visible_editable_textarea_scores_higher(self):
        good = {
            "tag": "textarea",
            "type": "",
            "role": "",
            "placeholder": "메시지를 입력",
            "ariaLabel": "",
            "visible": True,
            "editable": True,
            "disabled": False,
            "obscured": False,
            "footerLike": True,
            "rectTop": 900,
            "viewportHeight": 1200,
            "contentEditable": "",
        }
        bad = {
            "tag": "div",
            "type": "",
            "role": "",
            "placeholder": "",
            "ariaLabel": "",
            "visible": False,
            "editable": False,
            "disabled": True,
            "obscured": True,
            "footerLike": False,
            "rectTop": 10,
            "viewportHeight": 1200,
            "contentEditable": "",
        }
        assert _score_input_candidate_metadata(good, "chat-frame", "chat-frame") > _score_input_candidate_metadata(bad, "chat-frame", "page")


class TestInputCandidateClassification:
    def test_disabled_candidate_is_classified(self):
        category, reason = _classify_input_candidate_metadata({"disabled": True, "editable": False, "obscured": False})
        assert category == "input locator found but disabled"
        assert "disabled" in reason

    def test_obscured_candidate_is_classified(self):
        category, reason = _classify_input_candidate_metadata({"disabled": False, "editable": True, "obscured": True})
        assert category == "input locator found but obscured by overlay"
        assert "obscured" in reason