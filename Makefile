# Common tasks. Run from the repository root.
#   make install        Python + frontend dependencies
#   make db             apply database migrations
#   make data FILES="~/Downloads/2024_LoL_esports_match_data_from_OraclesElixir.csv ..."
#   make models         train and evaluate Elo / logistic regression (+ player model)
#   make player-model   add only the pre-game player model to the current version
#   make analytics      compute research indicators
#   make all FILES=...  data + models + analytics
#   make reload FILES=... same, after dropping all tables (for hosted databases)
#   make snapshot       write the website's static snapshot from the current database
#   make api / make web run the servers
#   make test           backend + frontend tests

PY ?= python

install:
	$(PY) -m pip install -r requirements-dev.txt
	cd frontend && npm ci

db:
	cd backend && $(PY) -m alembic upgrade head

data: db
	$(PY) -m pipelines.oracle_elixir.run $(if $(FILES),--import $(FILES),)

models:
	$(PY) -m machine_learning.training.train

# add the pre-game player model to an existing trained version (no Elo retraining)
player-model:
	$(PY) -m machine_learning.training.player_model

analytics:
	$(PY) -m analytics.run_all

all: data models analytics snapshot

# static snapshot of the API for the website (frontend/public/snapshot); run after any reload
snapshot:
	$(PY) -m backend.app.snapshot

# Rebuild from scratch: drop all tables first, then load. Use this on small
# hosted databases (e.g. Supabase free, 500 MB) so a reload does not need
# room for two copies of the data.
reset-db:
	cd backend && $(PY) -m alembic downgrade base && $(PY) -m alembic upgrade head

reload: reset-db data models analytics

api:
	$(PY) -m uvicorn backend.app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	$(PY) -m pytest
	cd frontend && npm run typecheck && npm test

build-web:
	cd frontend && npm run build

.PHONY: install db data models player-model analytics snapshot all reset-db reload api web test build-web
