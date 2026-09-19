# toy-pipeline

A four-stage teaching pipeline: `ingest` -> `normalize` -> `score` -> `report`.

Each stage is a module under `pipeline/`. The stages are meant to form a straight line, so a
reader should be able to name the order from the imports alone.
