// Fixed display order for the seven recipe categories. Any category not listed
// here sorts after all of these (index -1 sorts last, not first) rather than
// silently vanishing, so a typo'd or new category is visible instead of hidden.
export const CATEGORY_ORDER = [
  'before-any-code',
  'ci-release',
  'defect-work',
  'change-existing-code',
  'plugin-authoring',
  'quality-verification',
  'surface',
]

export const CATEGORY_LABELS = {
  'before-any-code': 'Before any code',
  'ci-release': 'CI & release',
  'defect-work': 'Defect work',
  'change-existing-code': 'Change existing code',
  'plugin-authoring': 'Plugin authoring',
  'quality-verification': 'Quality & verification',
  surface: 'Surface',
}
