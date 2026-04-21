import test from "node:test";
import assert from "node:assert/strict";

import { buildResultsModel, getSelectedPersonas } from "../assets/persona-logic.mjs";

function createFixture() {
  return {
    controlCategories: [
      { id: "controlsData", title: "Data Controls" },
      { id: "controlsApplication", title: "Application Controls" },
      { id: "controlsGovernance", title: "Governance Controls" },
    ],
    controls: [
      {
        id: "controlTraining",
        title: "Training Data Management",
        category: "controlsData",
        description: ["Protect training data."],
        personaIds: ["personaModelProvider"],
        riskIds: ["riskDataPoisoning"],
      },
      {
        id: "controlShared",
        title: "Shared Runtime Safeguard",
        category: "controlsApplication",
        description: ["Applies across provider and serving workflows."],
        personaIds: ["personaModelProvider", "personaModelServing"],
        riskIds: ["riskShared", "riskPromptInjection"],
      },
      {
        id: "controlRuntime",
        title: "Input Validation and Sanitization",
        category: "controlsApplication",
        description: ["Protect serving endpoints."],
        personaIds: ["personaModelServing"],
        riskIds: ["riskPromptInjection"],
      },
      {
        id: "controlRiskGovernance",
        title: "Risk Governance",
        category: "controlsGovernance",
        description: ["Provide governance oversight."],
        personaIds: ["personaGovernance"],
        riskIds: ["riskDataPoisoning", "riskShared", "riskPromptInjection"],
      },
    ],
    manualFallbackPersonaIds: ["personaModelServing", "personaGovernance"],
    personas: [
      {
        id: "personaModelProvider",
        title: "Model Provider",
        description: ["Train and distribute models."],
        questionIds: ["provider-q1"],
        matchMode: "guided",
        riskIds: ["riskDataPoisoning", "riskShared"],
        controlIds: ["controlTraining", "controlShared"],
        riskCount: 2,
        controlCount: 2,
      },
      {
        id: "personaModelServing",
        title: "AI Model Serving",
        description: ["Operate model serving systems."],
        questionIds: [],
        matchMode: "manual",
        riskIds: ["riskShared", "riskPromptInjection"],
        controlIds: ["controlShared", "controlRuntime"],
        riskCount: 2,
        controlCount: 2,
      },
      {
        id: "personaGovernance",
        title: "AI System Governance",
        description: ["Set policy and oversight."],
        questionIds: [],
        matchMode: "manual",
        riskIds: [],
        controlIds: ["controlRiskGovernance"],
        riskCount: 0,
        controlCount: 1,
      },
    ],
    questions: [
      {
        id: "provider-q1",
        personaId: "personaModelProvider",
        personaTitle: "Model Provider",
        prompt: "Are you training models for others?",
      },
    ],
    riskCategories: [
      { id: "risksSupplyChainAndDevelopment", title: "Supply Chain and Development" },
      { id: "risksRuntimeInputSecurity", title: "Runtime Input Security" },
    ],
    risks: [
      {
        id: "riskDataPoisoning",
        title: "Data Poisoning",
        category: "risksSupplyChainAndDevelopment",
        shortDescription: ["Training data is altered."],
        longDescription: [],
        examples: [],
        controlIds: ["controlTraining"],
        personaIds: ["personaModelProvider"],
      },
      {
        id: "riskShared",
        title: "Shared Exposure",
        category: "risksSupplyChainAndDevelopment",
        shortDescription: ["A shared risk."],
        longDescription: [],
        examples: [],
        controlIds: ["controlShared"],
        personaIds: ["personaModelProvider", "personaModelServing"],
      },
      {
        id: "riskPromptInjection",
        title: "Prompt Injection",
        category: "risksRuntimeInputSecurity",
        shortDescription: ["Prompts alter behavior."],
        longDescription: [],
        examples: [],
        controlIds: ["controlShared", "controlRuntime"],
        personaIds: ["personaModelServing"],
      },
    ],
  };
}

test("getSelectedPersonas supports a single guided persona match", () => {
  const fixture = createFixture();
  const selection = getSelectedPersonas(fixture, { "provider-q1": "yes" });

  assert.equal(selection.length, 1);
  assert.equal(selection[0].id, "personaModelProvider");
  assert.equal(selection[0].sourceLabel, "From answers");
  assert.deepEqual(selection[0].matchedQuestionPrompts, ["Are you training models for others?"]);
});

test("buildResultsModel supports guided plus manual multi-persona flows", () => {
  const fixture = createFixture();
  const results = buildResultsModel(fixture, { "provider-q1": "yes" }, ["personaModelServing"]);

  assert.deepEqual(
    results.includedPersonas.map((persona) => persona.id),
    ["personaModelProvider", "personaModelServing"],
  );
  assert.deepEqual(
    results.risks.map((risk) => risk.id),
    ["riskDataPoisoning", "riskShared", "riskPromptInjection"],
  );
  assert.deepEqual(
    results.controls.map((control) => control.id),
    ["controlTraining", "controlShared", "controlRuntime"],
  );
});

test("buildResultsModel allows manual fallback selection for AI Model Serving", () => {
  const fixture = createFixture();
  const results = buildResultsModel(fixture, {}, ["personaModelServing"]);

  assert.deepEqual(
    results.includedPersonas.map((persona) => persona.id),
    ["personaModelServing"],
  );
  assert.deepEqual(
    results.risks.map((risk) => risk.id),
    ["riskShared", "riskPromptInjection"],
  );
  assert.deepEqual(
    results.controls.map((control) => control.id),
    ["controlShared", "controlRuntime"],
  );
});

test("buildResultsModel deduplicates shared risks and controls", () => {
  const fixture = createFixture();
  const results = buildResultsModel(fixture, { "provider-q1": "yes" }, ["personaModelServing"]);

  assert.equal(results.risks.filter((risk) => risk.id === "riskShared").length, 1);
  assert.equal(results.controls.filter((control) => control.id === "controlShared").length, 1);
});

test("buildResultsModel keeps governance controls even when no direct risks are linked", () => {
  const fixture = createFixture();
  const results = buildResultsModel(fixture, {}, ["personaGovernance"]);

  assert.deepEqual(results.risks, []);
  assert.deepEqual(
    results.controls.map((control) => control.id),
    ["controlRiskGovernance"],
  );
  assert.deepEqual(
    results.directRisklessPersonas.map((persona) => persona.id),
    ["personaGovernance"],
  );
});
