import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import DataCollatorForTokenClassification
from collections import Counter
from datasets import Dataset
import transformers.tokenization_utils_base as tub
from tokenizers import Encoding

from src.models.components.bert_token_classifier import BertTokenClassifier
from src.datamodules.components.cora_label import LABEL_NAMES
from src.models.components.bert_tokenizer import bert_tokenizer

model = BertTokenClassifier(
    model_checkpoint="allenai/scibert_scivocab_uncased",
    output_size=13,
)
model.load_state_dict(torch.load("scibert-synthetic-50k-parscit.pt"))
model.eval()

en = Encoding()

def postprocess(batch, predictions, label_names):
    be = tub.BatchEncoding(batch, en)
    word_ids = be.word_ids()
    true_word_ids = [[id for id in word_id if id is not None] for word_id in word_ids]
    true_predictions = [
        [label_names[p] for p in prediction if p != -100] for prediction in predictions
    ]

    grouped_true_predictions = list()

    for word_id, true_prediction in zip(true_word_ids, true_predictions):
        grouped_true_prediction = list()

        current_group_predictions = list()
        for i in range(len(word_id)):
            current_group_predictions.append(true_prediction[i])

            if i + 1 == len(word_id):
                grouped_true_prediction.append(current_group_predictions)

            elif word_id[i] != word_id[i + 1]:
                grouped_true_prediction.append(current_group_predictions)
                current_group_predictions = list()

        grouped_true_predictions.append(grouped_true_prediction)

    merged_true_predictions = list()
    for grouped_true_prediction in grouped_true_predictions:
        merged_true_prediction = list(map(lambda l: Counter(l).most_common(1)[0][0], grouped_true_prediction))
        merged_true_predictions.append(merged_true_prediction)

    return merged_true_predictions


def predict_for_text(example: str):
    splitted_example = example.split()
    dict_data = {"tokens": [splitted_example]}
    dataset = Dataset.from_dict(dict_data)
    tokenized_example = dataset.map(
        lambda x: bert_tokenizer(x["tokens"], truncation=False, is_split_into_words=True),
        batched=True,
        remove_columns=dataset.column_names
    )
    dataloader = DataLoader(
        dataset=tokenized_example,
        batch_size=1,
        collate_fn=DataCollatorForTokenClassification(
            tokenizer=bert_tokenizer
        )
    )
    for batch in dataloader:
        outputs = model(**batch)
        preds = outputs.logits.argmax(dim=-1)
        # input_ids = batch["input_ids"]
        true_preds = postprocess(
            batch=batch,
            predictions=preds,
            label_names=LABEL_NAMES
        )

    # true_input_ids = [[id for id in input_id if id != 0 and id != 102 and id != 103] for input_id in input_ids]
    # raw_strings = [bert_tokenizer.decode(true_input_id) for true_input_id in true_input_ids]
    # tokens = [string.split() for string in raw_strings]
    tokens = splitted_example
    tagged_words = []
    for token, label in zip(tokens, true_preds[0]):
        tagged_word = f"<{label}>{token}</{label}>"
        tagged_words.append(tagged_word)
    result = " ".join(tagged_words)
    return result

