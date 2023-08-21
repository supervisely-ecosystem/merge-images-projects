import supervisely as sly
from supervisely.app.widgets import (
    Card,
    ReloadableArea,
    Button,
    SelectProject,
    Flexbox,
    Container,
    Text,
)

import src.globals as g
import src.ui.settings as settings

add_project_button = Button(
    text="",
    icon="zmdi zmdi-plus",
    icon_gap=0,
    button_type="success",
    widget_id="AddProjectButton",
)

lock_projects_button = Button(
    "Lock projects",
    icon="zmdi zmdi-lock",
)

projects_buttons_flexbox = Flexbox([add_project_button, lock_projects_button], gap=35)

projects_container = Container()
projects_ra = ReloadableArea(projects_container)

error_text = Text("At least two different projects should be selected", status="error")
error_text.hide()

unlock_projects_button = Button(
    "Unlock projects",
    icon="zmdi zmdi-lock-open",
)
unlock_projects_button.hide()

card = Card(
    title="1️⃣ Input projects",
    description="Select at least two different projects, which will be merged into one.",
    content=Container(
        [projects_ra, projects_buttons_flexbox, error_text],
    ),
    content_top_right=unlock_projects_button,
    collapsable=True,
    lock_message="Unlock the card by clicking the `Unlock projects` button in the top right corner.",
)


@add_project_button.click
def add_project_widgets():
    flexbox_id = len(projects_container._widgets)

    sly.logger.debug(
        f"Add project button was pressed, flexbox ID was set to {flexbox_id}."
    )

    remove_button = Button(
        text="",
        icon="zmdi zmdi-close",
        icon_gap=0,
        button_type="danger",
        button_size="small",
    )

    if flexbox_id < 2:
        remove_button.disable()

    @remove_button.click
    def remove_flexbox():
        del g.STATE.remove_buttons[flexbox_id]
        del g.STATE.project_selects[flexbox_id]

        sly.logger.debug(
            f"Remove button and project select was removed from global state with flexbox ID {flexbox_id}."
        )

        update_projects_widgets()

    project_select = SelectProject(
        workspace_id=g.STATE.selected_workspace,
        compact=True,
        show_label=False,
    )

    g.STATE.remove_buttons[flexbox_id] = remove_button
    g.STATE.project_selects[flexbox_id] = project_select

    sly.logger.debug(
        f"Remove button and project select was added to global state with flexbox ID {flexbox_id}."
    )

    update_projects_widgets()


def update_projects_widgets():
    remove_buttons = list(g.STATE.remove_buttons.values())
    project_selects = list(g.STATE.project_selects.values())

    if len(remove_buttons) != len(project_selects):
        sly.logger.error(
            f"Length of remove buttons ({len(remove_buttons)}) and project selects "
            f"({len(project_selects)}) is not equal. It will probably cause an error."
        )

        sly.app.show_dialog(
            title="Error in widget engine",
            description=(
                "For some reason, number of remove buttons and project selects is not equal. "
                "It will probably cause an error. It's recommended to restart the application."
            ),
            status="error",
        )

    projects_container._widgets = [
        Flexbox([project_select, remove_button], gap=20)
        for project_select, remove_button in zip(project_selects, remove_buttons)
    ]
    projects_ra.reload()


@lock_projects_button.click
def lock_project():
    project_ids = []

    for select_widget in g.STATE.project_selects.values():
        project_id = select_widget.get_selected_id()
        if project_id is not None and project_id not in project_ids:
            project_ids.append(project_id)

    if len(project_ids) < 2:
        error_text.show()

        sly.logger.warning(
            "Lock projects button was pressed, but less than 2 projects were selected."
        )

        return

    error_text.hide()

    g.STATE.project_ids = project_ids

    sly.logger.info(f"Following project IDs was saved in global state: {project_ids}")

    card.lock()
    card.collapse()

    settings.card.unlock()
    settings.card.uncollapse()

    lock_projects_button.hide()
    unlock_projects_button.show()


@unlock_projects_button.click
def unlock_project():
    settings.card.lock()
    settings.card.collapse()

    card.unlock()
    card.uncollapse()

    g.STATE.project_ids = None

    sly.logger.debug("Unlock projects button was pressed, project IDs was cleared.")

    lock_projects_button.show()
    unlock_projects_button.hide()


for _ in range(g.INIT_PROJECTS_COUNT):
    add_project_widgets()
