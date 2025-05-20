from transformers import AutoTokenizer, AutoModel
import torch

class CodeEmbedder:
    def __init__(self, model_name='microsoft/codebert-base'):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)

    def embed_code(self, code):
        inputs = self.tokenizer(code, return_tensors='pt', truncation=True, max_length=256)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[:, 0, :].squeeze().numpy() 