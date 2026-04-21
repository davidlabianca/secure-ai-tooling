export function dedupeInOrder(values) {
  const seen = new Set();
  const deduped = [];

  for (const value of values) {
    if (seen.has(value)) {
      continue;
    }

    seen.add(value);
    deduped.push(value);
  }

  return deduped;
}

function getQuestionMap(data) {
  return new Map(data.questions.map((question) => [question.id, question]));
}

export function getSelectedPersonas(data, answers = {}, manualSelectedIds = [], personaOverrides = {}) {
  const manualSelection = new Set(manualSelectedIds);
  const questionMap = getQuestionMap(data);

  return data.personas
    .filter((persona) => {
      const matchedQuestionIds = persona.questionIds.filter((questionId) => answers[questionId] === "yes");
      return matchedQuestionIds.length > 0 || manualSelection.has(persona.id);
    })
    .map((persona) => {
      const matchedQuestionIds = persona.questionIds.filter((questionId) => answers[questionId] === "yes");
      const sourceType = matchedQuestionIds.length > 0 ? "answers" : "manual";

      return {
        ...persona,
        included: personaOverrides[persona.id] ?? true,
        matchedQuestionIds,
        matchedQuestionPrompts: matchedQuestionIds
          .map((questionId) => questionMap.get(questionId)?.prompt)
          .filter(Boolean),
        sourceLabel: sourceType === "answers" ? "From answers" : "Added manually",
        sourceType,
      };
    });
}

function groupItemsByCategory(items, categoryDefinitions) {
  const groups = categoryDefinitions.map((category) => ({ category, items: [] }));
  const groupMap = new Map(groups.map((group) => [group.category.id, group]));

  for (const item of items) {
    const group = groupMap.get(item.category);
    if (group) {
      group.items.push(item);
    }
  }

  return groups.filter((group) => group.items.length > 0);
}

export function buildResultsModel(data, answers = {}, manualSelectedIds = [], personaOverrides = {}) {
  const selectedPersonas = getSelectedPersonas(data, answers, manualSelectedIds, personaOverrides);
  const includedPersonas = selectedPersonas.filter((persona) => persona.included);
  const includedPersonaIds = new Set(includedPersonas.map((persona) => persona.id));

  const riskLookup = new Map(data.risks.map((risk) => [risk.id, risk]));
  const controlLookup = new Map(data.controls.map((control) => [control.id, control]));

  const riskIds = dedupeInOrder(includedPersonas.flatMap((persona) => persona.riskIds));
  const controlIds = dedupeInOrder(includedPersonas.flatMap((persona) => persona.controlIds));
  const selectedRiskIdSet = new Set(riskIds);
  const selectedControlIdSet = new Set(controlIds);

  const risks = riskIds
    .map((riskId) => riskLookup.get(riskId))
    .filter(Boolean)
    .map((risk) => ({
      ...risk,
      personaIds: risk.personaIds.filter((personaId) => includedPersonaIds.has(personaId)),
      relatedControlIds: risk.controlIds.filter((controlId) => selectedControlIdSet.has(controlId)),
    }));

  const controls = controlIds
    .map((controlId) => controlLookup.get(controlId))
    .filter(Boolean)
    .map((control) => ({
      ...control,
      personaIds: control.personaIds.filter((personaId) => includedPersonaIds.has(personaId)),
      relatedRiskIds: control.riskIds.filter((riskId) => selectedRiskIdSet.has(riskId)),
    }));

  return {
    selectedPersonas,
    includedPersonas,
    riskGroups: groupItemsByCategory(risks, data.riskCategories),
    controlGroups: groupItemsByCategory(controls, data.controlCategories),
    risks,
    controls,
    directRisklessPersonas: includedPersonas.filter(
      (persona) => persona.riskIds.length === 0 && persona.controlIds.length > 0,
    ),
  };
}
