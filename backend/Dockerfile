FROM python:3.14-slim AS builder

WORKDIR /build

# MIT-licensed source/model: https://github.com/ankandrew/open-image-models
ARG PLATE_MODEL_URL=https://github.com/ankandrew/open-image-models/releases/download/assets/yolo-v9-s-608-license-plates-end2end.onnx
ARG PLATE_MODEL_SHA256=2b878b38d9aa07b6ddc3ea75c4ffcb39869bc5c218e0a14002f60ab2f7b0be9a

# MIT: https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT
ARG AUTHENTICITY_MODEL_URL=https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT/resolve/ac6ee457bea904a373065754107451793b56db00/onnx/model.onnx
ARG AUTHENTICITY_MODEL_SHA256=a42c7d740fbb345ba9a26d469b22f301d73089ce3c6da993877ed2b6965a8ba1

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir --prefix=/install -r requirements.lock
RUN mkdir -p /models \
    && python -c "import hashlib, pathlib, urllib.request; p=pathlib.Path('/models/license-plate.onnx'); urllib.request.urlretrieve('${PLATE_MODEL_URL}', p); actual=hashlib.sha256(p.read_bytes()).hexdigest(); expected='${PLATE_MODEL_SHA256}'; assert actual == expected, f'plate model checksum mismatch: {actual}'" \
    && python -c "import hashlib, pathlib, urllib.request; p=pathlib.Path('/models/community-forensics-deepfakedet-vit.onnx'); urllib.request.urlretrieve('${AUTHENTICITY_MODEL_URL}', p); actual=hashlib.sha256(p.read_bytes()).hexdigest(); expected='${AUTHENTICITY_MODEL_SHA256}'; assert actual == expected, f'authenticity model checksum mismatch: {actual}'"

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLATE_DETECTION_MODEL=/opt/models/license-plate.onnx \
    AUTHENTICITY_DETECTION_MODEL=/opt/models/community-forensics-deepfakedet-vit.onnx

WORKDIR /app

ARG UTIL_LINUX_VERSION=2.41.5-0+deb13u1
ARG LOGIN_VERSION=1:4.16.0-2+really2.41.5-0+deb13u1
RUN apt-get update \
    && apt-get install --yes --no-install-recommends --only-upgrade \
        "bsdutils=1:${UTIL_LINUX_VERSION}" \
        "libblkid1=${UTIL_LINUX_VERSION}" \
        "liblastlog2-2=${UTIL_LINUX_VERSION}" \
        "libmount1=${UTIL_LINUX_VERSION}" \
        "libsmartcols1=${UTIL_LINUX_VERSION}" \
        "libuuid1=${UTIL_LINUX_VERSION}" \
        "login=${LOGIN_VERSION}" \
        "mount=${UTIL_LINUX_VERSION}" \
        "util-linux=${UTIL_LINUX_VERSION}" \
    && rm -rf /var/lib/apt/lists/* \
    && find "$(python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" -maxdepth 1 \
        \( -name 'pip*' -o -name 'setuptools*' -o -name 'wheel*' \) \
        -exec rm -rf {} + \
    && addgroup --system app \
    && adduser --system --ingroup app app

COPY --from=builder /install /usr/local
COPY --from=builder /models /opt/models
COPY app ./app
COPY scripts ./scripts

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
