et[split_name])))
            )

    dataset["train"] = dataset["train"].shuffle(seed=training_args.seed)

    data_args.train_val_split = None if "validation" in dataset else data_args.train_val_split
    if isinstance(data_args.train_val_split, float) and data_args.train_val_split > 0.0:
        split = dataset["train"].train_test_split(data_args.train_val_split, seed=training_args.seed)
        dataset["train"] = split["train"]
        dataset["validation"] = split["test"]

    categories = None
    try:
        if isinstance(dataset["train"].features["objects"], dict):
            cat_feature = dataset["train"].features["objects"]["category"].feature
        else:
            cat_feature = dataset["train"].features["objects"].feature["category"]

        if hasattr(cat_feature, "names"):
            categories = cat_feature.names
    except (AttributeError, KeyError):
        pass

    if categories is None:
        # Category is a Value type (not ClassLabel) — scan dataset to discover labels
        logger.info("Category feature is not ClassLabel — scanning dataset to discover category labels...")
        unique_cats = set()
        for example in dataset["train"]:
            cats = example["objects"]["category"]
            if isinstance(cats, list):
                unique_cats.update(cats)
     