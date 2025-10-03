# ml/models.py
# -*- coding: utf-8 -*-
import torch, torch.nn as nn

class LSTMClassifier(nn.Module):
    def __init__(self, n_features=5, hidden=64, n_layers=1, dropout=0.0):
        super().__init__()
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden,
                            num_layers=n_layers, batch_first=True, dropout=dropout if n_layers>1 else 0.0)
        self.head = nn.Sequential(
            nn.LayerNorm(hidden),
            nn.Linear(hidden, 1)
        )
    def forward(self, x):
        # x: (B, T, F)
        out, _ = self.lstm(x)
        last = out[:, -1, :]
        logit = self.head(last).squeeze(-1)
        return logit
