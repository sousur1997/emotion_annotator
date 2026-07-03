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
