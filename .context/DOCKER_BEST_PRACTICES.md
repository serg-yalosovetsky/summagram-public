# Dockerfile Design Principles

This document outlines the best practices and design principles for creating Dockerfiles in this project. Adhering to these guidelines ensures fast builds, small image sizes, and maintainable infrastructure.

## 1. Leverage Build Caching efficiently
-   **Use mount caches**: For package managers like `pip` and `apt`, use BuildKit's cache mounts to persist downloaded packages between builds.
    ```dockerfile
    RUN --mount=type=cache,target=/root/.cache/pip pip install ...
    ```
-   **Order matters**: Place stable instructions (installing system deps) before volatile instructions (copying source code).

## 2. Optimize RUN Commands
-   **Split long commands**: Instead of creating one massive `RUN` instruction with endless `&&`, split distinct logical steps into separate `RUN` commands.
    -   *Why*: Improves caching. If step 3 fails or changes, steps 1 and 2 don't need to re-run. Easier to debug.
-   **Group related ops**: Keep related operations (update + install) together to avoid using stale cache.

## 3. Documentation & Logging
-   **Comment complex steps**: Explain *why* a package is installed or a flag is used.
-   **Log errors**: Ensure commands output useful error messages.
-   **Echo progress**: Use `echo "Installing X..."` in complex scripts if needed.

## 4. Prefer Pre-built Binaries & Images
-   **Base Images**: Start with specialized images (e.g., `vllm/vllm-openai`, `pytorch/...`) instead of building from scratch.
-   **Wheels**: Download pre-compiled `.whl` files for heavy libraries (`flash-attn`, `autoawq`) to avoid hour-long compilation times.

## 5. Dependency Management
-   **Stay current**: Try to use the latest stable versions of libraries (unless pinned for compatibility).
-   **Pin versions**: For production stability, pin versions in `requirements.txt` but audit them regularly.

## 6. Minimize Rebuild Time
-   **Separate dependency installation**: Copy `requirements.txt` and install dependencies *before* copying the rest of the application code.
-   **Multi-stage builds**: Use a `builder` stage for heavy lifting and a lightweight `runtime` stage for the final image.

## 7. Intelligent Layer Ordering
-   **Volatile last**: Transformations that change frequently (application code, config files) should be at the very bottom of the Dockerfile.
-   **Stable first**: OS updates, system libraries, and base environment setup go at the top.

## 8. Minimize Image Size
-   **Slim base images**: Use `-slim` or `-alpine` variants where possible (check compatibility with ML wheels).
-   **Clean up**: Remove apt caches (`rm -rf /var/lib/apt/lists/*`) and temporary build artifacts after installation.
-   **Exclude files**: Use `.dockerignore` to prevent uploading `venv`, `.git`, or data directories to the build context.
