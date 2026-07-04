# Annotation Web App (PWA)

A small Progressive Web App for collecting emotion labels on media items. It is intended for researchers and annotators who need a fast, intuitive interface for building emotion-labelled datasets.

**Demo / Project page:** https://sousur1997.github.io/emotion_annotator/

**Purpose**
- Collect consistent emotion labels for images, video frames, or short clips to support tasks like classification, segmentation, or affective computing research.
- Provide a lightweight tool for quick annotation sessions, pilot studies, or small-scale dataset creation without heavy infrastructure.

**Who should use this**
- Researchers needing fast, manual emotion annotations.
- Small teams preparing labelled data for model training or evaluation.
- Educators demonstrating annotation workflows in class or workshops.

**How to use (user-focused)**
1. Open the app in your browser (see demo link to see it in action).
2. Load or navigate to the media item you want to label (the app UI presents the item and annotation controls).
3. Select one or more emotion labels from the visible options (e.g., happy, sad, angry) and add optional notes if available.
4. Save or submit the annotation — the UI records the label and moves to the next item.
5. Repeat until your annotation batch is complete. Export or collect the saved annotations from the app's storage (see project code for storage/export hooks).

**Design principles**
- Minimal, distraction-free UI to reduce annotator fatigue.
- Fast keyboard or click-driven workflows for high throughput.
- Local-first operation: works offline for short sessions and stores annotations locally.

**Files (quick reference)**
- `index.html` — app shell and markup
- `app.js` — main application logic (annotation flow, UI behavior)
- `style.css` — visual styling
- `manifest.json` — PWA manifest
- `service-worker.js` — offline support

**Contributing**
- PRs, bug reports, and suggestions welcome. If you add new label sets or export features, please include a short usage note.

**License**
- See the repository for license details.
# Emotion Annotator PWA

This is a static Progressive Web App for annotating audio/video with continuous emotion values on a timeline.

## Run locally

Because the app uses a service worker, it should be served over HTTP instead of opened directly from the filesystem.

From the project folder, run:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

## Publish to GitHub Pages

1. Create a GitHub repository.
2. Push the project to GitHub.
3. Open the repository on GitHub.
4. Go to Settings → Pages.
5. Set Source to "Deploy from a branch".
6. Choose the `main` branch and `/ (root)`.
7. Save and wait for the site to build.

Your app will be available at:

```text
https://<your-username>.github.io/<your-repo-name>/
```

## Notes

- The app works best when served over HTTPS or localhost.
- On mobile devices, install it from the browser after the site is deployed.
