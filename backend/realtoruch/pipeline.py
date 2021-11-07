"""Dataflow streaming entry point. Install the [gcp] extra to execute."""

import argparse
import hashlib
import json
import os
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, SetupOptions


class PersistObservation(beam.DoFn):
    def __init__(self, config_secret):
        self.config_secret = config_secret

    def setup(self):
        from google.cloud import secretmanager

        payload = (
            secretmanager.SecretManagerServiceClient()
            .access_secret_version(name=self.config_secret)
            .payload.data
        )
        # A secret JSON object supplies DATABASE_URL and application security settings at runtime.
        for key, value in json.loads(payload).items():
            os.environ[key] = str(value)
        from .db import Session

        self.session_factory = Session

    def process(self, message):
        from pydantic import ValidationError
        from .schemas import RawListing
        from .ingest import ingest

        try:
            raw = RawListing.model_validate_json(message)
        except (ValidationError, ValueError):
            # Do not echo input, contact data or validation values into logs or dead-letter metadata.
            yield beam.pvalue.TaggedOutput(
                "invalid",
                json.dumps(
                    {"event_sha256": hashlib.sha256(message).hexdigest(), "error": "invalid_observation"}
                ).encode(),
            )
            return
        if raw.is_demo:
            yield beam.pvalue.TaggedOutput(
                "invalid",
                json.dumps(
                    {"event_sha256": hashlib.sha256(message).hexdigest(), "error": "demo_in_production"}
                ).encode(),
            )
            return
        with self.session_factory.begin() as session:
            result = ingest(session, raw)
        # Database failures deliberately propagate so Dataflow retries; idempotency handles redelivery.
        yield json.dumps(result).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_subscription", required=True)
    parser.add_argument("--dead_letter_topic", required=True)
    parser.add_argument("--config_secret", required=True)
    known, beam_args = parser.parse_known_args()
    options = PipelineOptions(beam_args)
    options.view_as(StandardOptions).streaming = True
    options.view_as(SetupOptions).save_main_session = True
    if os.environ.get("BEAM_SETUP_FILE"):
        options.view_as(SetupOptions).setup_file = os.environ["BEAM_SETUP_FILE"]
    if os.environ.get("BEAM_REQUIREMENTS_FILE"):
        options.view_as(SetupOptions).requirements_file = os.environ["BEAM_REQUIREMENTS_FILE"]
    with beam.Pipeline(options=options) as pipeline:
        output = (
            pipeline
            | "Read observations" >> beam.io.ReadFromPubSub(subscription=known.input_subscription)
            | "Normalize and commit"
            >> beam.ParDo(PersistObservation(known.config_secret)).with_outputs("invalid", main="persisted")
        )
        output.invalid | "Quarantine invalid events" >> beam.io.WriteToPubSub(known.dead_letter_topic)


if __name__ == "__main__":
    main()
