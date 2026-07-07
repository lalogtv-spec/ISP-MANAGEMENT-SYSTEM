# Colab Bridge Guide

This project can export a Colab-ready bundle for:

- face enrollment analysis
- payment history review
- overdue snapshot analysis

## Export From Django

Run:

```bash
python manage.py export_colab_bundle --include-models
```

Optional zip output:

```bash
python manage.py export_colab_bundle --include-models --output C:\tmp\colab_bundle.zip
```

The export contains:

- `clients.csv`
- `payments.csv`
- `overdue_snapshot.csv`
- `facial_biometrics.jsonl`
- `face_images_manifest.csv`
- `face_images/`
- `summary.json`

## Starter Notebook

Open or upload:

- `backend/colab/colab_bridge_starter.ipynb`
- `backend/colab/raw_face_training.ipynb`

That notebook loads the bundle, reads Colab secrets safely, and provides starter analysis for:

- enrolled face templates
- payment history
- overdue risk

The raw face training notebook uses the exported images and checks whether validation accuracy reaches 60% or better on the current dataset.

## Colab Secrets

Do not paste API keys into chat or hardcode them in the notebook.
Use one of these:

- Colab Secrets / `userdata`
- environment variables inside the notebook
- Google Drive files mounted into Colab

The notebooks now mount Drive automatically when they detect Colab and default to:

- `/content/drive/MyDrive/colab_exports`
- `/content/drive/MyDrive/colab_output`

## Choosing A Source

Set this in Colab to pick where the notebook reads data from:

```python
os.environ["COLAB_SOURCE_MODE"] = "drive"
```

or

```python
os.environ["COLAB_SOURCE_MODE"] = "firebase"
```

Drive uses the exported zip bundle. Firebase reads Firestore collections directly.

## How To Connect Drive

Drive is not connected until you run the mount cell in Colab and authorize access.

Steps:

1. Open the notebook in Colab.
2. Run the cell that contains:

```python
from google.colab import drive
drive.mount('/content/drive')
```

3. Click the authorization link Colab shows.
4. Sign in to your Google account.
5. Paste the verification code back into Colab.

After that, the notebook can read and write files in `MyDrive`.

## How To Connect Firebase

If you choose Firebase source mode, you also need a Firebase service account JSON available in Colab.

1. Upload the service account JSON to Drive or place it in a secure Drive folder.
2. Set `FIREBASE_CREDENTIALS_PATH` to that JSON path.
3. Set `COLAB_SOURCE_MODE=firebase`.
4. Run the notebook.

Before using Firebase mode for face training, sync the facial biometrics first:

```bash
python manage.py sync_to_firebase --colab
```

That will sync clients, payments, overdue-related data, and facial biometrics with the raw image payloads needed by the raw face training notebook.

Example:

```python
import os

os.environ["GOOGLE_API_KEY"] = "your-key-here"
```

If you want to override the default Drive paths:

```python
os.environ["COLAB_DRIVE_EXPORT_DIR"] = "/content/drive/MyDrive/colab_exports"
os.environ["COLAB_DRIVE_OUTPUT_DIR"] = "/content/drive/MyDrive/colab_output"
os.environ["COLAB_BUNDLE_PATH"] = "/content/drive/MyDrive/colab_exports/colab_bundle.zip"
```

If you use Colab Secrets:

```python
from google.colab import userdata

os.environ["GOOGLE_API_KEY"] = userdata.get("GOOGLE_API_KEY")
os.environ["FIREBASE_CREDENTIALS_PATH"] = userdata.get("FIREBASE_CREDENTIALS_PATH")
```

## Suggested Workflow

1. Export the bundle from Django.
2. Upload or mount the bundle in Colab.
3. Train or analyze face records from `facial_biometrics.jsonl`.
4. Analyze `payments.csv` and `overdue_snapshot.csv` for reporting or anomaly detection.
5. Save results back to Drive or export them for Django to consume.

## Important Note

The current app stores enrolled face templates, not raw face photos.
That means Colab can analyze the biometric templates and build supporting analytics,
but it should not be treated as a live face-recognition backend unless you add a
separate image-capture pipeline.
