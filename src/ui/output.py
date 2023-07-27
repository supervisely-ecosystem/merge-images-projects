from typing import Optional, Tuple

import supervisely as sly

from supervisely.app.widgets import (
    Container,
    Card,
    Button,
    ProjectThumbnail,
    Progress,
    Text,
    Input,
    Select,
    Field,
)

import src.globals as g

dataset_structure_select = Select(
    items=[Select.Item(value=value) for value in g.DATASET_CONFLICTS]
)
dataset_structure_field = Field(
    title="Dataset structure",
    description="How datasets should be structured in the output project.",
    content=dataset_structure_select,
)

output_project_input = Input(minlength=1, placeholder="Output project name")
output_project_field = Field(
    title="Output project name",
    description="Choose the name for output project, if not specified, it will be generated automatically.",
    content=output_project_input,
)

merge_button = Button("Merge")

merge_progress = Progress()

result_text = Text()
result_text.hide()

project_thumbnail = ProjectThumbnail()
project_thumbnail.hide()

card = Card(
    title="3️⃣ Output",
    description="Choose the name for output project and start the merging process.",
    content=Container(
        [
            dataset_structure_field,
            output_project_field,
            merge_button,
            merge_progress,
            result_text,
            project_thumbnail,
        ]
    ),
    lock_message="Lock settings on step 2️⃣.",
    collapsable=True,
)
card.lock()
card.collapse()


@merge_button.click
def generate():
    result_text.hide()
    project_thumbnail.hide()
    merge_button.text = "Merging..."
    create_project(output_project_input.get_value())

    # * ###################################
    # * ###### Add your logic here. #######
    # * ###################################

    with merge_progress(
        message="Merging projects...", total=len(g.STATE.project_ids)
    ) as pbar:
        for input_project_id in g.STATE.project_ids:
            input_datasets = g.api.dataset.get_list(input_project_id)
            input_dataset_ids = [dataset.id for dataset in input_datasets]

            # TODO: Depending on structure settings, create datasets: single for all, single for each project, single for each dataset.

            if dataset_structure_select.get_value() == "Merge into one dataset":
                raise NotImplementedError(
                    "Merging into one dataset is not implemented yet."
                )
            elif (
                dataset_structure_select.get_value()
                == "Separate dataset for each project"
            ):
                raise NotImplementedError(
                    "Merging into separate datasets is not implemented yet."
                )
            elif dataset_structure_select.get_value() == "Save original names":
                input_dataset_names = [dataset.name for dataset in input_datasets]
                output_dataset_ids = [
                    create_dataset(dataset_name) for dataset_name in input_dataset_names
                ]

                for input_dataset_id, output_dataset_id in zip(
                    input_dataset_ids, output_dataset_ids
                ):
                    upload_dataset(
                        input_project_id, input_dataset_id, output_dataset_id
                    )

            pbar.update(1)

    result_text.text = "Successfully merged projects."
    result_text.status = "success"
    result_text.show()

    project_thumbnail.set(g.api.project.get_info_by_id(g.STATE.output_project_id))
    project_thumbnail.show()

    # * Returning button texts to it's default state.
    merge_button.text = "Merge"


def create_project(project_name: Optional[str]) -> int:
    if not project_name:
        project_name = "Merged project"

    g.STATE.output_project_id = g.api.project.create(
        g.STATE.selected_workspace, project_name, change_name_if_conflict=True
    ).id


def upload_dataset(input_project_id, input_dataset_id, output_dataset_id):
    input_image_infos = g.api.image.get_list(input_dataset_id)
    input_project_meta = sly.ProjectMeta.from_json(
        g.api.project.get_meta(input_project_id)
    )
    input_anns = [
        sly.Annotation.from_json(ann_json, input_project_meta)
        for ann_json in g.api.annotation.download_json_batch(
            input_dataset_id,
            [image_info.id for image_info in input_image_infos],
        )
    ]

    output_image_infos = []
    output_anns = []

    for image_info, ann in zip(input_image_infos, input_anns):
        # TODO: If merging into one dataset, check for conflicts and rename (or skip) images.
        # ??? If merging into single dataset for each project same check maybe neeeded?

        img_size = (image_info.height, image_info.width)
        output_ann = update_annotation(ann, img_size)

        output_image_infos.append(image_info)
        output_anns.append(output_ann)

    for batched_image_infos, batched_anns in zip(
        sly.batched(input_image_infos),
        sly.batched(output_anns),
    ):
        batched_image_ids = [image_info.id for image_info in batched_image_infos]
        batched_image_names = [image_info.name for image_info in batched_image_infos]
        batched_image_metas = [image_info.meta for image_info in batched_image_infos]

        uploaded_image_infos = g.api.image.upload_ids(
            output_dataset_id,
            ids=batched_image_ids,
            names=batched_image_names,
            metas=batched_image_metas,
        )

        uploaded_image_ids = [image_info.id for image_info in uploaded_image_infos]

        g.api.annotation.upload_anns(uploaded_image_ids, batched_anns)


def update_annotation(input_ann: sly.Annotation, img_size: Tuple[int, int]):
    output_labels = [update_label(label) for label in input_ann.labels]
    output_ann = sly.Annotation(img_size=img_size, labels=output_labels)
    return output_ann


def update_label(input_label: sly.Label):
    output_project_meta = g.STATE.output_project_meta
    if not output_project_meta:
        output_project_meta = sly.ProjectMeta()

    if input_label.obj_class in output_project_meta.obj_classes:
        return input_label

    new_obj_class = input_label.obj_class
    new_label = input_label

    for obj_class in output_project_meta.obj_classes:
        if obj_class.name == input_label.obj_class.name:
            if obj_class.geometry_type != input_label.obj_class.geometry_type:
                # TODO: Based on conflict settings, rename or skip the class and return None.

                new_obj_class = input_label.obj_class.clone(
                    name=f"{input_label.obj_class.name}_{input_label.obj_class.geometry_type}"  # ! Need string representation of geometry type.
                )
                new_label = input_label.clone(obj_class=new_obj_class)

    result_project_meta = output_project_meta.add_obj_class(new_obj_class)

    g.STATE.output_project_meta = result_project_meta
    g.api.project.update_meta(g.STATE.output_project_id, g.STATE.output_project_meta)

    return new_label


def create_dataset(dataset_name: str) -> int:
    return g.api.dataset.create(
        g.STATE.output_project_id, dataset_name, change_name_if_conflict=True
    ).id


"""
def merge_classes():
    sly.logger.debug("Starting merging project meta.")
    result_project_meta = sly.ProjectMeta()

    for project_id in g.STATE.project_ids:
        project_info = g.api.project.get_info_by_id(project_id)
        project_meta = sly.ProjectMeta.from_json(g.api.project.get_meta(project_id))
        obj_classes = project_meta.obj_classes

        for obj_class in obj_classes:
            if obj_class.name in [
                obj_class.name for obj_class in result_project_meta.obj_classes
            ]:
                if g.STATE.settings["class_conflict"] == "Skip":
                    continue
                elif g.STATE.settings["class_conflict"] == "Rename":
                    obj_class = obj_class.clone(
                        name=f"{project_info.name}_{obj_class.name}"
                    )

            result_project_meta = result_project_meta.add_obj_class(obj_class)

    print(result_project_meta)

    sly.logger.debug("Finished merging project meta.")
"""

"""

"""
