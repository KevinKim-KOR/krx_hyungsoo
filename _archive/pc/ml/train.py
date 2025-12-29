# ml/train.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, time, math, argparse, torch
from torch.utils.data import DataLoader, random_split
from ml.datasets import SeqDataset
from ml.models import LSTMClassifier

def get_device():
    return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

def train_once(codes, seq_len=60, epochs=10, batch=256, lr=1e-3, hidden=64, layers=1, dropout=0.0, threshold=0.0):
    ds = SeqDataset(codes, seq_len=seq_len, threshold=threshold)
    n_train = int(len(ds)*0.8); n_val = len(ds)-n_train
    tr, va = random_split(ds, [n_train, n_val], generator=torch.Generator().manual_seed(0))
    # Development Rules: 병렬 금지 → num_workers=0
    tr_ld = DataLoader(tr, batch_size=batch, shuffle=True,  num_workers=0)
    va_ld = DataLoader(va, batch_size=batch, shuffle=False, num_workers=0)

    dev = get_device()
    model = LSTMClassifier(hidden=hidden, n_layers=layers, dropout=dropout).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    best_val = math.inf; best_path = None
    for ep in range(1, epochs+1):
        model.train(); loss_sum = 0.0
        for xb, yb in tr_ld:
            xb, yb = xb.to(dev), yb.float().to(dev)
            opt.zero_grad()
            logit = model(xb)
            loss  = loss_fn(logit, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            loss_sum += loss.item()*xb.size(0)
        tr_loss = loss_sum/len(tr)

        # val
        model.eval(); val_loss=0.0; correct=0; total=0
        with torch.no_grad():
            for xb, yb in va_ld:
                xb, yb = xb.to(dev), yb.float().to(dev)
                logit = model(xb)
                val_loss += loss_fn(logit, yb).item()*xb.size(0)
                pred = (torch.sigmoid(logit)>0.5).long()
                correct += (pred==yb.long()).sum().item()
                total   += yb.numel()
        val_loss/=len(va); acc=correct/total if total else 0.0
        print(f"[EP{ep:03d}] tr_loss={tr_loss:.4f} val_loss={val_loss:.4f} acc={acc:.3f}")

        if val_loss < best_val:
            best_val = val_loss
            os.makedirs("models", exist_ok=True)
            best_path = os.path.join("models", f"lstm_best.pt")
            torch.save({"model":model.state_dict(),
                        "meta":{"hidden":hidden,"layers":layers,"dropout":dropout,"seq_len":seq_len}}, best_path)

    return {"best_val":best_val, "best_path":best_path}

def main():
    ap = argparse.ArgumentParser(description="DL training (GPU 지원)")
    ap.add_argument("--codes", default="005930,000660,069500,091160,133690,305720,373220")
    ap.add_argument("--seq", type=int, default=60)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--layers", type=int, default=1)
    ap.add_argument("--dropout", type=float, default=0.0)
    ap.add_argument("--th", type=float, default=0.0, help="분류 임계 (다음날 r1 > th)")
    args = ap.parse_args()

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    t0=time.time()
    out = train_once(codes, seq_len=args.seq, epochs=args.epochs, batch=args.batch,
                     lr=args.lr, hidden=args.hidden, layers=args.layers, dropout=args.dropout, threshold=args.th)
    os.makedirs("reports/train", exist_ok=True)
    js = os.path.join("reports","train", f"train_{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(js,"w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print("DONE:", out, "elapsed:", round(time.time()-t0,1),"s")

if __name__=="__main__":
    raise SystemExit(main())
