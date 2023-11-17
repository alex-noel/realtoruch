import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("react-native", async () => vi.importActual("react-native-web"));
vi.mock("react-native-safe-area-context", () => ({ SafeAreaView: "div" }));
vi.mock("lucide-react-native/icons/check", () => ({ default: "span" }));
vi.mock("lucide-react-native/icons/x", () => ({ default: "span" }));

import { Field, nativeFieldPurposeProps } from "../src/components/UI";

describe("shared Field semantics", () => {
  it("associates the label and maps email and password purposes to web autofill hints", () => {
    const email = renderToStaticMarkup(
      <Field
        label="Email address"
        value=""
        onChange={() => {}}
        inputPurpose="email"
      />,
    );
    expect(email).toContain('aria-labelledby="');
    expect(email).toContain('type="email"');
    expect(email).toContain('autoComplete="email"');

    const current = renderToStaticMarkup(
      <Field
        label="Password"
        value=""
        onChange={() => {}}
        inputPurpose="current-password"
      />,
    );
    const next = renderToStaticMarkup(
      <Field
        label="Choose password"
        value=""
        onChange={() => {}}
        inputPurpose="new-password"
      />,
    );
    expect(current).toContain('type="password"');
    expect(current).toContain('autoComplete="current-password"');
    expect(next).toContain('type="password"');
    expect(next).toContain('autoComplete="new-password"');
  });

  it("announces invalid fields and connects helper and error text by ID", () => {
    const valid = renderToStaticMarkup(
      <Field
        label="Name"
        value="Ada"
        onChange={() => {}}
        helperText="Use your legal name."
      />,
    );
    expect(valid).toContain("Use your legal name.");
    expect(valid).toContain('aria-describedby="_R_0_-helper"');
    expect(valid).not.toContain('aria-invalid="true"');

    const invalid = renderToStaticMarkup(
      <Field
        label="Email"
        value="bad"
        onChange={() => {}}
        error="Enter a valid email."
        errorId="email-error"
        helperText="We will not share it."
      />,
    );
    expect(invalid).toContain('aria-invalid="true"');
    expect(invalid).toContain('aria-describedby="email-error _R_0_-helper"');
    expect(invalid).toContain('id="email-error"');
    expect(invalid).toContain("We will not share it.");
  });

  it("preserves numeric input mode and uses distinct single-line and multiline submission", () => {
    const numeric = renderToStaticMarkup(
      <Field label="Area" value="" onChange={() => {}} numeric />,
    );
    expect(numeric).toContain('inputMode="numeric"');

    const email = renderToStaticMarkup(
      <Field label="Email" value="" onChange={() => {}} inputPurpose="email" />,
    );
    expect(email).toContain('type="email"');

    const single = renderToStaticMarkup(
      <Field
        label="Subject"
        value=""
        onChange={() => {}}
        onSubmitEditing={() => {}}
      />,
    );
    expect(single).toContain('enterKeyHint="done"');
    const multiline = renderToStaticMarkup(
      <Field label="Message" value="" onChange={() => {}} multiline />,
    );
    expect(multiline).toContain("<textarea");
    expect(multiline).not.toContain('enterKeyHint="done"');
  });

  it("maps email and password purposes to native content and keyboard hints", () => {
    expect(nativeFieldPurposeProps("email")).toEqual({
      autoComplete: "email",
      textContentType: "emailAddress",
      keyboardType: "email-address",
    });
    expect(nativeFieldPurposeProps("current-password")).toEqual({
      autoComplete: "current-password",
      secureTextEntry: true,
      textContentType: "password",
    });
    expect(nativeFieldPurposeProps("new-password")).toEqual({
      autoComplete: "new-password",
      secureTextEntry: true,
      textContentType: "newPassword",
    });
  });
});
