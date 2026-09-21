FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# **루트로 돌리지 않는다.** 이 이미지가 하는 일은 마이그레이션 · 시드 · API 서빙이라
# 파일을 쓸 일이 없는데, 루트로 두면 컨테이너 안에서 코드 실행이 일어났을 때 막을
# 것이 하나 줄어든다. **상주 서비스가 같은 이미지로 뜨면서 그 이유가 더 강해졌다.**
RUN addgroup --system erp && adduser --system --ingroup erp erp

COPY --chown=erp:erp . .

USER erp
ENTRYPOINT ["./docker-entrypoint.sh"]
