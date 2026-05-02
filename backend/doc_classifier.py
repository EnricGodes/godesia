"""Document vs. photo classifier using CLIP embeddings.

Phase 1: Zero-shot classification via CLIP text/image similarity.
Phase 3: Fine-tuned sklearn LogisticRegression on CLIP embeddings.
"""

import pickle
from pathlib import Path
from typing import Optional

MODEL_PATH = Path(__file__).parent / "doc_classifier.pkl"

DOC_PROMPTS = [
    "a scanned historical document",
    "a handwritten certificate",
    "an official registry page",
    "a death certificate",
    "a birth record",
    "a marriage record",
    "a newspaper clipping",
    "a typed official form",
]
PHOTO_PROMPTS = [
    "a photograph of a person",
    "a family portrait",
    "a personal photograph",
    "a group photo of people outdoors",
]

THRESH_AUTO_DOC   = 0.75  # >= → auto-document
THRESH_REVIEW_LOW = 0.35  # <  → auto-not-document; in between → pending review

# Module-level cache so CLIP loads only once per server process
_clip_model = None
_clip_preprocess = None
_clip_text_features = None


def _get_clip():
    """Lazy-load CLIP ViT-B-32 (openai weights). Raises ImportError if open_clip not installed."""
    global _clip_model, _clip_preprocess, _clip_text_features
    if _clip_model is not None:
        return _clip_model, _clip_preprocess, _clip_text_features

    import open_clip  # noqa: PLC0415
    import torch      # noqa: PLC0415

    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai"
    )
    model.eval()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")

    all_prompts = DOC_PROMPTS + PHOTO_PROMPTS
    tokens = tokenizer(all_prompts)
    with torch.no_grad():
        text_features = model.encode_text(tokens)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    _clip_model = model
    _clip_preprocess = preprocess
    _clip_text_features = text_features
    return model, preprocess, text_features


def clip_available() -> bool:
    """Return True if open_clip and torch are importable."""
    try:
        import open_clip  # noqa: F401
        import torch      # noqa: F401
        return True
    except ImportError:
        return False


def get_image_embedding(image_path: str) -> Optional[list]:
    """Return the CLIP image embedding (512-dim float32) for one image, or None on error."""
    try:
        import torch  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        model, preprocess, _ = _get_clip()
        img = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            emb = model.encode_image(img)
            emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.squeeze(0).cpu().numpy()
    except Exception:
        return None


def classify_zero_shot(image_path: str) -> Optional[float]:
    """Score of being a document [0, 1] via CLIP zero-shot softmax. None on error."""
    try:
        import torch  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        model, preprocess, text_features = _get_clip()
        img = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            img_feat = model.encode_image(img)
            img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
            sims = (img_feat @ text_features.T).squeeze(0)
            probs = sims.softmax(dim=-1).cpu().numpy()
        return float(probs[: len(DOC_PROMPTS)].sum())
    except Exception:
        return None


def classify_finetuned(image_path: str) -> Optional[float]:
    """Score via fine-tuned LogisticRegression. None if model file doesn't exist or error."""
    if not MODEL_PATH.exists():
        return None
    try:
        emb = get_image_embedding(image_path)
        if emb is None:
            return None
        clf = pickle.loads(MODEL_PATH.read_bytes())
        classes = list(clf.classes_)
        proba = clf.predict_proba([emb])[0]
        if 1 in classes:
            return float(proba[classes.index(1)])
        return float(proba[-1])
    except Exception:
        return None


def classify_image(image_path: str) -> Optional[float]:
    """Main entry point: use fine-tuned model if available, else zero-shot. Returns doc score [0,1]."""
    score = classify_finetuned(image_path)
    if score is None:
        score = classify_zero_shot(image_path)
    return score


def train_finetuned(db_conn, photos_dir: Path) -> dict:
    """Train a LogisticRegression classifier on CLIP embeddings of labeled photos.

    Labeled = doc_origin IN ('human', 'tag', 'clip_auto') AND is_document IN (0, 1)
              AND is_downloaded = 1.

    Returns dict with: ok (bool), n_samples, n_pos, n_neg, cv_accuracy, cv_std, error (str).
    """
    try:
        import numpy as np                                        # noqa: PLC0415
        from sklearn.linear_model import LogisticRegression      # noqa: PLC0415
        from sklearn.model_selection import cross_val_score      # noqa: PLC0415
    except ImportError as exc:
        return {"ok": False, "error": f"Missing dependency: {exc}"}

    rows = db_conn.execute(
        """
        SELECT id, filename, is_document
        FROM photos
        WHERE doc_origin IN ('human', 'tag', 'clip_auto')
          AND is_document IN (0, 1)
          AND is_downloaded = 1
        """
    ).fetchall()

    X, y = [], []
    for row in rows:
        path = str(photos_dir / row["filename"])
        emb = get_image_embedding(path)
        if emb is not None:
            X.append(emb)
            y.append(int(row["is_document"]))

    if len(X) < 20:
        return {"ok": False, "error": f"Only {len(X)} labeled samples with embeddings, need ≥ 20"}

    X_arr = np.array(X)  # noqa: F821 (imported above inside try)
    y_arr = np.array(y)
    n_pos = int(y_arr.sum())
    n_neg = int(len(y_arr) - n_pos)

    if n_pos < 5 or n_neg < 5:
        return {
            "ok": False,
            "error": f"Need ≥ 5 of each class (got {n_pos} documents, {n_neg} non-documents)",
        }

    clf = LogisticRegression(max_iter=1000, C=1.0)
    cv = min(5, n_pos, n_neg)
    scores = cross_val_score(clf, X_arr, y_arr, cv=cv, scoring="accuracy")
    clf.fit(X_arr, y_arr)

    MODEL_PATH.write_bytes(pickle.dumps(clf))

    return {
        "ok": True,
        "n_samples": len(X),
        "n_pos": n_pos,
        "n_neg": n_neg,
        "cv_accuracy": float(scores.mean()),
        "cv_std": float(scores.std()),
    }
