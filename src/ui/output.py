from typing import Optional, Tuple

import supervisely as sly
from supervisely.collection.key_indexed_collection import DuplicateKeyError

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
def merge():
    g.STATE.output_project_meta = None
    g.STATE.output_project_id = None
    result_text.hide()
    project_thumbnail.hide()
    merge_button.text = "Merging..."
    create_project(output_project_input.get_value())

    dataset_structure = dataset_structure_select.get_value()
    sly.logger.debug(
        f"Dataset structure is set to {dataset_structure}, starting merging..."
    )

    if dataset_structure == "Merge into one dataset":
        output_dataset_id = create_dataset("Merged dataset")

    sly.logger.debug(
        f"Starting iteration over {len(g.STATE.project_ids)} projects to merge..."
    )

    with merge_progress(
        message="Merging projects...", total=len(g.STATE.project_ids)
    ) as pbar:
        for input_project_id in g.STATE.project_ids:
            input_datasets = g.api.dataset.get_list(input_project_id)
            input_dataset_ids = [dataset.id for dataset in input_datasets]

            if dataset_structure == "Merge into one dataset":
                for input_dataset_id in input_dataset_ids:
                    upload_dataset(
                        input_project_id, input_dataset_id, output_dataset_id
                    )
            elif dataset_structure == "Separate dataset for each project":
                input_project_name = g.api.project.get_info_by_id(input_project_id).name
                output_dataset_id = create_dataset(input_project_name)

                for input_dataset_id in input_dataset_ids:
                    upload_dataset(
                        input_project_id, input_dataset_id, output_dataset_id
                    )

            elif dataset_structure == "Save original names":
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

    merge_button.text = "Merge"

    sly.logger.info(
        f"Successfully merged {len(g.STATE.project_ids)} projects. App finished."
    )


def create_project(project_name: Optional[str]) -> int:
    if not project_name:
        project_name = "Merged project"

    g.STATE.output_project_id = g.api.project.create(
        g.STATE.selected_workspace, project_name, change_name_if_conflict=True
    ).id

    sly.logger.info(
        f"Created output project with ID {g.STATE.output_project_id} and saved it to state."
    )


def upload_dataset(input_project_id, input_dataset_id, output_dataset_id):
    sly.logger.info(
        f"Starting uploading dataset with ID {input_dataset_id} to dataset with ID {output_dataset_id}..."
    )

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

    output_image_ids = []
    output_image_names = []
    output_image_metas = []
    output_anns = []

    existing_images_names = [
        image_info.name for image_info in g.api.image.get_list(output_dataset_id)
    ]

    for image_info, ann in zip(input_image_infos, input_anns):
        input_image_id = image_info.id
        input_image_name = image_info.name
        input_image_meta = image_info.meta

        if input_image_name in existing_images_names:
            sly.logger.debug(
                f"Image with name {input_image_name} already exists in output dataset."
            )

            if g.STATE.conflict_settings.image_conflicts == "Skip":
                sly.logger.debug(
                    f"Conflict resolution is set to 'Skip', skipping image with name {input_image_name}..."
                )
                continue
            elif g.STATE.conflict_settings.image_conflicts == "Rename":
                input_image_name = g.api.image.get_free_name(
                    output_dataset_id, input_image_name
                )

                sly.logger.debug(
                    f"Conflict resolution is set to 'Rename', the image was renamed to {input_image_name}."
                )

        img_size = (image_info.height, image_info.width)
        output_ann = update_annotation(ann, img_size)

        output_image_ids.append(input_image_id)
        output_image_names.append(input_image_name)
        output_image_metas.append(input_image_meta)
        output_anns.append(output_ann)

    sly.logger.debug(
        f"Successfully updated annotations for {len(output_anns)} images and prepared them for upload."
    )

    for (
        batched_image_ids,
        batched_image_names,
        batched_image_metas,
        batched_anns,
    ) in zip(
        sly.batched(output_image_ids),
        sly.batched(output_image_names),
        sly.batched(output_image_metas),
        sly.batched(output_anns),
    ):
        uploaded_image_infos = g.api.image.upload_ids(
            output_dataset_id,
            ids=batched_image_ids,
            names=batched_image_names,
            metas=batched_image_metas,
        )

        uploaded_image_ids = [image_info.id for image_info in uploaded_image_infos]

        g.api.annotation.upload_anns(uploaded_image_ids, batched_anns)

        sly.logger.debug(
            f"Successfully uploaded batch of {len(uploaded_image_ids)} images with annotations."
        )

    sly.logger.info(
        f"Finished uploading dataset with ID {input_dataset_id} to dataset with ID {output_dataset_id}."
    )


def update_annotation(input_ann: sly.Annotation, img_size: Tuple[int, int]):
    output_labels = [
        update_label(label) for label in input_ann.labels if update_label(label)
    ]
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

    for tag in input_label.tags:
        if tag.meta not in output_project_meta.tag_metas:
            sly.logger.debug(f"Adding tag meta {tag.meta.name} to output project meta.")

            output_project_meta = output_project_meta.add_tag_meta(tag.meta)

    for obj_class in output_project_meta.obj_classes:
        if obj_class.name == input_label.obj_class.name:
            if obj_class.geometry_type != input_label.obj_class.geometry_type:
                sly.logger.debug(
                    f"Output project meta already contanins object class with name {obj_class.name}, "
                    f"Existing geometry type: {obj_class.geometry_type}, new geometry type: "
                    f"{input_label.obj_class.geometry_type}."
                )

                if g.STATE.conflict_settings.class_conflicts == "Skip":
                    sly.logger.debug(
                        "Conflict resolution is set to 'Skip', skipping label with "
                        f"object class {input_label.obj_class.name}..."
                    )
                    return
                elif g.STATE.conflict_settings.class_conflicts == "Rename":
                    sly.logger.debug(
                        f"Conflict resolution is set to 'Rename', renaming object class "
                        f"{input_label.obj_class.name} according to its geometry type..."
                    )

                    new_obj_class = input_label.obj_class.clone(
                        name=f"{input_label.obj_class.name}_{input_label.obj_class.geometry_type.geometry_name()}"
                    )
                    new_label = input_label.clone(obj_class=new_obj_class)

    try:
        output_project_meta = output_project_meta.add_obj_class(new_obj_class)
        g.STATE.output_project_meta = output_project_meta
        g.api.project.update_meta(
            g.STATE.output_project_id, g.STATE.output_project_meta
        )
    except DuplicateKeyError:
        sly.logger.debug(
            f"Output project meta already contanins object class with name {new_obj_class.name}. "
            "Project meta was not updated."
        )

    return new_label


def create_dataset(dataset_name: str) -> int:
    return g.api.dataset.create(
        g.STATE.output_project_id, dataset_name, change_name_if_conflict=True
    ).id
