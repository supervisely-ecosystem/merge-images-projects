import supervisely as sly

from supervisely.app.widgets import Card, Field, Select, Container, Button

import src.globals as g
import src.ui.output as output

image_conflict_select = Select(
    items=[Select.Item(value=value) for value in g.IMAGE_CONFLICTS]
)
image_conflict_field = Field(
    title="Image conflict resolution",
    description="How to resolve conflicts if images have the same names.",
    content=image_conflict_select,
)

class_conflict_select = Select(
    items=[Select.Item(value=value) for value in g.CLASS_CONFLICTS]
)
class_conflict_field = Field(
    title="Class conflict resolution",
    description="How to resolve conflicts if classes have the same names.",
    content=class_conflict_select,
)

lock_settings_button = Button(
    text="Lock settings",
    icon="zmdi zmdi-lock",
)

unlock_settings_button = Button(
    text="Unlock settings",
    icon="zmdi zmdi-lock-open",
)
unlock_settings_button.hide()

card = Card(
    title="2️⃣ Conflicts resolution",
    description="Choose the way to resolve conflicts between projects.",
    content=Container(
        [
            image_conflict_field,
            class_conflict_field,
            lock_settings_button,
        ],
    ),
    content_top_right=unlock_settings_button,
    lock_message="Select the projects on step 1️⃣.",
    collapsable=True,
)
card.lock()
card.collapse()


@lock_settings_button.click
def lock_settings():
    g.STATE.conflict_settings = g.ConflictSettings(
        image_conflicts=image_conflict_select.get_value(),
        class_conflicts=class_conflict_select.get_value(),
    )

    sly.logger.info(
        f"Following settings were saved in global state: {g.STATE.conflict_settings}"
    )

    card.lock()
    card.collapse()

    lock_settings_button.hide()
    unlock_settings_button.show()

    output.card.unlock()
    output.card.uncollapse()


@unlock_settings_button.click
def unlock_settings():
    card.unlock()
    card.uncollapse()

    g.STATE.settings = None

    sly.logger.debug("Unlock settings button was pressed, settings were reset.")

    lock_settings_button.show()
    unlock_settings_button.hide()

    output.card.lock()
    output.card.collapse()
