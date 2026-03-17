---
name: mirror_clock
description: "Standard operating procedure for normalizing and reading mirror-reflected clock faces."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: A reliable horizontal flip transformation to normalize the clock face before reading the time.
2. Run `python -m tools mirror_corrector datasets/mira/images/2.png`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Instruct the agent to always flip the image horizontally first when encountering a mirror clock task before attempting to read the hands. If still failing, The agent consistently struggles with the mental rotation/reflection of the clock face. A physical tool to flip the image will remove the ambiguity and allow the model to read the clock as a standard face.
