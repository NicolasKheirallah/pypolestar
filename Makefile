SOURCE=		pypolestar
PROTO_DIR=	$(SOURCE)/proto
PROTO_FILES=	$(wildcard $(PROTO_DIR)/*.proto)

PYTHON?=	uv run python

all:

lint:
	uv run ruff check $(SOURCE) tests

reformat:
	uv run ruff check --select I --fix $(SOURCE) tests
	uv run ruff format $(SOURCE) tests

test:
	uv run pytest --ruff --ruff-format $(SOURCE) tests

proto:
	$(PYTHON) -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(PROTO_DIR) \
		--grpc_python_out=$(PROTO_DIR) \
		$(PROTO_FILES)
	sed -i.bak -E 's/^import (polestar_[a-z_]+_pb2) as (.*)$$/from . import \1 as \2/' $(PROTO_DIR)/polestar_*_pb2.py $(PROTO_DIR)/polestar_*_pb2_grpc.py
	rm $(PROTO_DIR)/polestar_*_pb2.py.bak $(PROTO_DIR)/polestar_*_pb2_grpc.py.bak
