---
name: gta_perception
description: "Mastery SOP for gta_perception using strategy text-first event banner read."
level: mid
depends_on: []
applicability_conditions: "Use when the question asks for names of teams, event titles, scores, dates, or any answer likely printed in the image.; Use when the image is a sports photo and the decisive evidence is likely on a scoreboard, sideline board, jersey text, or venue signage.; Use when small localized text is likely more reliable than global scene description."
        ---

## SOP
1. Confirm this applies: Use when the question asks for names of teams, event titles, scores, dates, or any answer likely printed in the image.; Use when the image is a sports photo and the decisive evidence is likely on a scoreboard, sideline board, jersey text, or venue signage.; Use when small localized text is likely more reliable than global scene description.
2. Run `python -m tools localized_text_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (Avoid when the question is purely about counting visible people/objects.; Avoid when the target is a non-text visual attribute such as color, pose, weather, or relative position.; Avoid when the relevant evidence is already large and obvious enough to answer directly without zoom.), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
