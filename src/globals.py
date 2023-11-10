import os
from collections import namedtuple

import supervisely as sly

from dotenv import load_dotenv

ConflictSettings = namedtuple(
    "ConflictSettings",
    [
        "image_conflicts",
        "class_conflicts",
    ],
)

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))
api = sly.Api.from_env()

SLY_APP_DATA_DIR = sly.app.get_data_dir()

IMAGE_CONFLICTS = ["Skip", "Rename"]
CLASS_CONFLICTS = ["Skip", "Rename"]
DATASET_CONFLICTS = [
    "Save original names",
    "Merge into one dataset",
    "Separate dataset for each project",
]
INIT_PROJECTS_COUNT = 2


class State:
    def __init__(self):
        self.selected_team = sly.io.env.team_id()
        self.selected_workspace = sly.io.env.workspace_id()

        self.remove_buttons = {}
        self.project_selects = {}

        self.project_ids = None

        self.conflict_settings = None

        self.output_project_id = None
        self.output_project_meta = None


STATE = State()
