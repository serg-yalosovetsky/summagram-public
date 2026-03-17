# Error 13: Docker WSL GPU Error in Model Orchestrator

## Symptoms
Model orchestrator fails to start `summagram_new_sglang_text` container, triggering a 500 error on the Docker API layer. The log states `nvidia-container-cli: initialization error: WSL environment detected but no adapters were found`.

## Investigation Notes
- **Symptoms**: The model orchestrator container tries to start the `sglang_text` container with GPU capabilities requested (`DeviceRequest(count=1, capabilities=[["gpu"]])`). The Docker daemon rejects this request because it cannot find the NVIDIA adapters in the WSL environment.
- **Scope**: This failure prevents the local text model container from starting up, leading to 503 Service Unavailable errors when the backend attempts to communicate with the model orchestrator.
- **Root Cause**: The host WSL environment is misconfigured or has broken GPU drivers. Docker is configured to use the NVIDIA container toolkit, but the toolkit cannot communicate with the Windows host's GPU drivers.
- **Evidence**: The error message originates from `nvidia-container-cli` running inside the Docker daemon context.

## Plan (Pending User Review)
Since the application must exclusively run on GPU or NPU, we should not disable GPU requests in the code. The problem lies with the host environment.

**Step 1: Verify Host GPU Availability**
- **Action**: Run `nvidia-smi` inside the WSL terminal to check if the GPU is visible to WSL.
- **Validation**: If `nvidia-smi` fails or shows no devices, the host WSL environment needs driver repairs.

**Step 2: Repair WSL / Docker GPU Integration**
- **Action**: The user needs to verify that:
  - The latest NVIDIA drivers are installed on the Windows Host.
  - If using Docker Desktop, Settings > Resources > WSL Integration is enabled, and the GPU feature is enabled.
  - If using Docker Engine inside WSL directly, the NVIDIA Container Toolkit is installed and configured correctly per NVIDIA's WSL2 instructions.
- **Validation**: Run `docker run --rm --gpus all ubuntu nvidia-smi` to ensure Docker can successfully allocate the GPU.

**Step 3: Future-proofing for NPU (Optional based on user specs)**
- **Action**: If the user plans to use an NPU instead of a GPU in this environment, we may need to parameterize the `DeviceRequest` capabilities to allow requesting NPUs instead of strictly checking for `[["gpu"]]`.
- **Validation**: Ensure container launches with the appropriate hardware accelerator requested.

## Status
Unresolved (Pending Environment Fix)
