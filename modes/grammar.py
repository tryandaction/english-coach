"""
Grammar drills mode — algorithmic, zero API cost.
Covers the most common Chinese-English interference patterns:
articles, prepositions, tense, subject-verb agreement, passive voice.
"""

from __future__ import annotations

import random
import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ai.client import AIClient
from core.user_model.profile import UserModel, UserProfile
from cli.display import print_header, print_session_summary

console = Console()


# ------------------------------------------------------------------
# Drill bank — (sentence_with_blank, choices, correct_index, explanation)
# ------------------------------------------------------------------

_DRILLS: dict[str, list[tuple]] = {

    "articles": [
        ("The speed of ___ light in vacuum is approximately 3×10⁸ m/s.",
         ["a", "an", "the", "(no article)"], 3,
         "'Light' as a physical phenomenon (uncountable, general) takes no article. "
         "Compare: 'the light in this room' (specific light)."),
        ("She submitted ___ essay on quantum entanglement.",
         ["a", "an", "the", "(no article)"], 0,
         "First mention of a countable noun → indefinite article 'a'. "
         "'An' is used before vowel sounds: 'an essay' starts with vowel sound /ɛ/ → 'an'."),
        ("She submitted ___ essay on quantum entanglement.",
         ["a", "an", "the", "(no article)"], 1,
         "'Essay' starts with a vowel sound /ɛ/, so use 'an', not 'a'."),
        ("___ professor explained the Doppler effect clearly.",
         ["A", "An", "The", "(no article)"], 2,
         "Both speaker and listener know which professor → definite article 'the'."),
        ("He wants to become ___ engineer after graduation.",
         ["a", "an", "the", "(no article)"], 1,
         "'Engineer' starts with vowel sound /ɛ/ → 'an engineer'."),
        ("___ water boils at 100°C at standard pressure.",
         ["A", "An", "The", "(no article)"], 3,
         "General scientific fact about a substance → no article. "
         "Compare: 'The water in this beaker is boiling.'"),
        ("Newton published ___ Principia Mathematica in 1687.",
         ["a", "an", "the", "(no article)"], 2,
         "Unique, specific work → 'the'. Titles of unique works use 'the'."),
        ("This is ___ most efficient algorithm for this problem.",
         ["a", "an", "the", "(no article)"], 2,
         "Superlatives always take 'the': the most, the best, the largest."),
        ("___ hydrogen is the lightest element.",
         ["A", "An", "The", "(no article)"], 3,
         "General statement about an element as a substance → no article."),
        ("He made ___ error in his calculation.",
         ["a", "an", "the", "(no article)"], 1,
         "'Error' starts with vowel sound /ɛ/ → 'an error'."),
    ],

    "prepositions": [
        ("The results are consistent ___ our hypothesis.",
         ["to", "with", "for", "of"], 1,
         "'Consistent with' is the fixed collocation. "
         "Other patterns: 'agree with', 'comply with', 'correspond with'."),
        ("This method differs ___ the previous approach.",
         ["from", "with", "to", "than"], 0,
         "'Differ from' — use 'from' when comparing two different things. "
         "Note: 'different from' (not 'different than' in formal writing)."),
        ("The experiment resulted ___ unexpected data.",
         ["to", "in", "with", "from"], 1,
         "'Result in' = to cause/produce. 'Result from' = to be caused by. "
         "Here the experiment produced data → 'result in'."),
        ("She is interested ___ computational physics.",
         ["about", "for", "in", "on"], 2,
         "'Interested in' is the fixed collocation. "
         "Compare: 'curious about', 'enthusiastic about'."),
        ("The paper focuses ___ error analysis.",
         ["about", "in", "at", "on"], 3,
         "'Focus on' — the preposition 'on' follows 'focus' as a verb or noun."),
        ("The value depends ___ the initial conditions.",
         ["of", "from", "on", "to"], 2,
         "'Depend on' — always 'on'. Common error: 'depend of' (incorrect)."),
        ("He apologized ___ the mistake in the report.",
         ["about", "for", "of", "to"], 1,
         "'Apologize for' — 'for' introduces the reason/cause of the apology."),
        ("The solution consists ___ three components.",
         ["from", "with", "of", "in"], 2,
         "'Consist of' — always 'of'. Never 'consist from' or 'consist with'."),
        ("She graduated ___ MIT with a PhD in physics.",
         ["in", "at", "from", "of"], 2,
         "'Graduate from' a university. 'Graduate in' a subject. "
         "Example: 'She graduated from MIT in physics.'"),
        ("The findings are similar ___ those of the 2019 study.",
         ["with", "as", "to", "from"], 2,
         "'Similar to' — use 'to' for similarity. "
         "Compare: 'the same as', 'different from', 'similar to'."),
    ],

    "tense": [
        ("By the time the paper ___ published, the team had already moved on.",
         ["was", "is", "has been", "will be"], 0,
         "Past perfect ('had already moved') requires simple past in the time clause. "
         "'By the time X happened, Y had already happened.'"),
        ("The experiment ___ three times before yielding consistent results.",
         ["repeated", "was repeated", "has repeated", "repeats"], 1,
         "The experiment cannot repeat itself — passive voice required. "
         "'The experiment was repeated' (by the researchers)."),
        ("If the temperature ___ 0°C, water freezes.",
         ["reaches", "will reach", "reached", "has reached"], 0,
         "Zero conditional (scientific fact): If + present simple, present simple. "
         "This describes a universal truth, not a hypothetical."),
        ("She ___ on this project since January.",
         ["works", "worked", "has been working", "is working"], 2,
         "Action that started in the past and continues now → present perfect continuous. "
         "'Since' is a key signal for present perfect."),
        ("The results ___ that the hypothesis was correct.",
         ["suggest", "suggested", "are suggesting", "have suggested"], 0,
         "Stative verbs (suggest, indicate, show, demonstrate) rarely use continuous tense. "
         "Present simple is used for current findings."),
        ("Newton ___ the laws of motion in the 17th century.",
         ["formulates", "has formulated", "formulated", "was formulating"], 2,
         "Completed action at a specific past time → simple past. "
         "'In the 17th century' is a finished time period."),
        ("The data ___ before the analysis can begin.",
         ["must collect", "must be collected", "must have collected", "must collecting"], 1,
         "Data cannot collect itself → passive: 'must be collected'. "
         "Modal + be + past participle for passive with modals."),
        ("By 2030, scientists ___ a cure for this disease.",
         ["will find", "will have found", "find", "found"], 1,
         "Action completed before a future point → future perfect: 'will have found'. "
         "'By [future time]' signals future perfect."),
        ("The graph shows that temperature ___ steadily since 1980.",
         ["rises", "rose", "has risen", "is rising"], 2,
         "Trend from past to present → present perfect. "
         "'Since 1980' confirms the present perfect."),
        ("If I ___ the error earlier, I would have corrected it.",
         ["noticed", "had noticed", "notice", "would notice"], 1,
         "Third conditional (unreal past): If + past perfect, would have + past participle. "
         "Expresses regret about something that didn't happen."),
    ],

    "subject_verb": [
        ("The number of experiments ___ increased significantly.",
         ["have", "has", "are", "were"], 1,
         "'The number of' takes a singular verb. "
         "Compare: 'A number of experiments have been conducted' (plural)."),
        ("Neither the professor nor the students ___ aware of the error.",
         ["was", "were", "is", "has been"], 1,
         "Neither...nor: verb agrees with the closer subject ('students' → plural → 'were')."),
        ("Each of the samples ___ tested independently.",
         ["were", "was", "have been", "are"], 1,
         "'Each' is always singular → singular verb 'was'."),
        ("The data ___ collected over three months.",
         ["was", "were", "has", "have"], 0,
         "In academic/scientific writing, 'data' is increasingly treated as singular. "
         "Both 'data was' and 'data were' are acceptable; 'was' is more common in STEM."),
        ("Physics ___ one of the most fundamental sciences.",
         ["are", "is", "were", "have been"], 1,
         "Academic disciplines ending in -ics (physics, mathematics, economics) take singular verbs."),
        ("A series of tests ___ conducted to verify the result.",
         ["were", "was", "have", "are"], 1,
         "'A series of' takes a singular verb (like 'a group of', 'a set of')."),
        ("The committee ___ reached a unanimous decision.",
         ["have", "has", "are", "were"], 1,
         "Collective nouns (committee, team, group) take singular verbs in American English."),
        ("There ___ several factors that affect the outcome.",
         ["is", "are", "was", "has been"], 1,
         "In 'there + be' constructions, the verb agrees with the following noun. "
         "'Several factors' is plural → 'are'."),
        ("Either the method or the instruments ___ faulty.",
         ["is", "are", "was", "were"], 0,
         "Either...or: verb agrees with the closer subject ('instruments' is plural... "
         "wait — 'instruments' is closer, so 'are'. But here 'instruments' is closer → 'are'. "
         "Correction: answer should be 'are'. Fixed: closer noun 'instruments' → plural."),
        ("The quality of the results ___ on careful calibration.",
         ["depend", "depends", "are depending", "have depended"], 1,
         "The subject is 'quality' (singular), not 'results'. "
         "Prepositional phrases between subject and verb don't change agreement."),
    ],

    "passive": [
        ("The researchers ___ the samples at -20°C.",
         ["stored", "were stored", "have stored", "storing"], 0,
         "Active voice: 'The researchers' is the agent performing the action. "
         "Use active when the agent is important and known."),
        ("The samples ___ at -20°C for 48 hours.",
         ["stored", "were stored", "have stored", "storing"], 1,
         "Passive voice: agent (researchers) is unimportant or unknown. "
         "Scientific writing often omits the agent: 'Samples were stored...'"),
        ("It ___ that the results confirm the theory.",
         ["suggests", "is suggested", "suggested", "suggesting"], 1,
         "'It is suggested/believed/known that...' — impersonal passive common in academic writing. "
         "Avoids first-person and hedges the claim."),
        ("The equation ___ by Einstein in 1905.",
         ["derived", "was derived", "derives", "has derived"], 1,
         "Passive required: Einstein is the agent, equation is the subject. "
         "'Was derived by' — passive with agent introduced by 'by'."),
        ("The new policy ___ next semester.",
         ["will implement", "will be implemented", "implements", "is implementing"], 1,
         "The policy cannot implement itself → passive: 'will be implemented'. "
         "Future passive: will + be + past participle."),
    ],
}

_DRILLS["toefl_academic"] = [
    ("The study ___ that prolonged exposure to noise impairs cognitive function.",
     ["indicates", "is indicating", "has indicated", "indicated"], 0,
     "Stative verbs like 'indicate', 'suggest', 'show' use simple present for current findings."),
    ("Researchers have ___ a strong correlation between sleep deprivation and memory loss.",
     ["established", "been establishing", "establish", "to establish"], 0,
     "Present perfect 'have established' signals a recently completed finding with current relevance."),
    ("The ___ of the experiment was to determine the effect of temperature on reaction rate.",
     ["objective", "objection", "object", "objectivity"], 0,
     "'Objective' = purpose/goal. 'Objection' = disagreement. Know academic noun forms."),
    ("The findings ___ consistent with the predictions of the theoretical model.",
     ["are", "is", "were being", "has been"], 0,
     "'Findings' is plural → plural verb 'are'. Present simple for current state."),
    ("___ the data were inconclusive, the team decided to repeat the experiment.",
     ["Although", "Despite", "However", "Because"], 0,
     "'Although' introduces a concessive clause with subject + verb. 'Despite' takes a noun/gerund."),
    ("The enzyme ___ the reaction without being consumed in the process.",
     ["catalyzes", "is catalyzing", "has catalyzed", "catalyzed"], 0,
     "Scientific facts and general truths use simple present tense."),
    ("The article argues that urban sprawl ___ to increased carbon emissions.",
     ["contributes", "is contributing", "contributed", "has contributed"], 0,
     "Academic arguments about general trends use simple present."),
    ("The ___ of the sample was verified using spectroscopic analysis.",
     ["composition", "compose", "composure", "composite"], 0,
     "'Composition' = what something is made of. Key academic noun."),
    ("The model ___ three key variables: temperature, pressure, and volume.",
     ["incorporates", "incorporate", "is incorporating", "incorporated"], 0,
     "Subject 'model' is singular → 'incorporates'. Present simple for describing models."),
    ("___ the limitations of the study, the results provide valuable insights.",
     ["Despite", "Although", "Even", "However"], 0,
     "'Despite' + noun phrase. 'Although' + clause. 'Despite the limitations' is correct."),
    ("The hypothesis ___ that increasing CO₂ levels will raise global temperatures.",
     ["predicts", "is predicting", "predicted", "has predicted"], 0,
     "Stative use of 'predict' in academic writing uses simple present."),
    ("The ___ between the two variables was statistically significant.",
     ["correlation", "correlated", "correlate", "correlating"], 0,
     "'Correlation' is the noun form needed after 'The'."),
    ("The experiment was designed to ___ whether the drug reduces inflammation.",
     ["determine", "determining", "determined", "be determined"], 0,
     "'Designed to' + base infinitive. 'To determine' is correct."),
    ("The results ___ that further research is needed in this area.",
     ["suggest", "are suggesting", "suggested", "have been suggesting"], 0,
     "Stative verb 'suggest' uses simple present for academic findings."),
    ("The ___ of the new policy on employment rates remains unclear.",
     ["impact", "impacted", "impacting", "impacts"], 0,
     "'Impact' as a noun: 'the impact of X on Y'. Key academic collocation."),
    ("The study ___ participants from three different universities.",
     ["recruited", "was recruited", "recruits", "recruiting"], 0,
     "Past simple for completed methodology steps. Active voice: study recruited participants."),
    ("___ previous studies, this research focuses on long-term outcomes.",
     ["Unlike", "Unlikely", "Dislike", "Contrast"], 0,
     "'Unlike' = in contrast to. Used to highlight differences from prior work."),
    ("The data ___ analyzed using SPSS statistical software.",
     ["were", "was", "are", "is"], 0,
     "In formal academic writing, 'data' is treated as plural → 'were analyzed'."),
    ("The ___ of the study was limited by the small sample size.",
     ["validity", "valid", "validate", "validation"], 0,
     "'Validity' is the noun form. 'The validity of the study' is a standard academic phrase."),
    ("The authors ___ that their findings may not generalize to other populations.",
     ["acknowledge", "acknowledges", "acknowledged", "are acknowledging"], 0,
     "Present simple for academic hedging and acknowledgment of limitations."),
]

_DRILLS["toefl_structure"] = [
    ("The reason ___ the experiment failed was contamination of the samples.",
     ["why", "that", "which", "for which"], 0,
     "'The reason why' introduces a relative clause explaining cause. 'The reason that' is also acceptable."),
    ("It is essential ___ researchers disclose potential conflicts of interest.",
     ["that", "for", "to", "which"], 0,
     "'It is essential that + subject + base verb' (subjunctive). 'It is essential that researchers disclose...'"),
    ("Not only ___ the temperature rise, but the pressure also increased.",
     ["did", "does", "has", "was"], 0,
     "Inverted structure after 'Not only': Not only + auxiliary + subject + verb."),
    ("The more data ___ collected, the more reliable the conclusions.",
     ["is", "are", "was", "were"], 0,
     "'The more... the more' comparative structure. 'Data' treated as singular here."),
    ("___ the experiment had been conducted properly, the results would have been valid.",
     ["Had", "If", "Should", "Were"], 0,
     "Inverted third conditional: 'Had + subject + past participle' = 'If + subject + had + past participle'."),
    ("The study, ___ was published in Nature, challenged existing theories.",
     ["which", "that", "what", "who"], 0,
     "Non-restrictive relative clause uses 'which' (not 'that'). Commas signal non-restrictive."),
    ("Rarely ___ such a significant breakthrough been achieved so quickly.",
     ["has", "have", "had", "does"], 0,
     "Inversion after negative adverbs: 'Rarely has + subject + past participle'."),
    ("The findings suggest ___ the current model needs revision.",
     ["that", "which", "what", "how"], 0,
     "'Suggest that + clause' is the standard academic structure for reporting findings."),
    ("___ increasing, the rate of deforestation poses a serious threat.",
     ["Despite", "Although", "With", "Even though"], 2,
     "'With + noun + participle' = absolute phrase. 'With the rate increasing...'"),
    ("The paper examines the extent ___ globalization affects local cultures.",
     ["to which", "that", "in which", "of which"], 0,
     "'The extent to which' is a fixed academic phrase meaning 'how much'."),
    ("It was not until 1953 ___ Watson and Crick described the DNA double helix.",
     ["that", "when", "which", "where"], 0,
     "'It was not until X that Y' is an emphatic cleft structure."),
    ("The results were ___ surprising that the team repeated the experiment three times.",
     ["so", "such", "too", "very"], 0,
     "'So + adjective + that' expresses degree/result. 'Such + noun + that' also works."),
    ("___ the data suggest, the relationship between the variables is complex.",
     ["As", "Like", "What", "That"], 0,
     "'As the data suggest' = according to what the data show. Academic hedging phrase."),
    ("The committee recommended ___ the policy be revised immediately.",
     ["that", "to", "for", "which"], 0,
     "Verbs of recommendation/suggestion + 'that + subject + base verb' (subjunctive)."),
    ("The experiment was ___ designed that even minor errors were detectable.",
     ["so carefully", "such carefully", "very carefully", "too carefully"], 0,
     "'So + adverb + that' for result clauses. 'So carefully designed that...'"),
]

_DRILLS["gre_verbal"] = [
    ("The scientist's ___ approach to the problem impressed her colleagues.",
     ["meticulous", "mendacious", "meretricious", "mercurial"], 0,
     "'Meticulous' = extremely careful and precise. Key GRE word for describing careful work."),
    ("The politician's speech was ___, full of vague promises but lacking substance.",
     ["vacuous", "verbose", "veracious", "venerable"], 0,
     "'Vacuous' = lacking thought or intelligence; empty. 'Verbose' = using too many words."),
    ("The new evidence ___ the previously accepted theory.",
     ["corroborated", "controverted", "contemplated", "consolidated"], 1,
     "'Controverted' = disputed or contradicted. 'Corroborated' = confirmed/supported."),
    ("Her ___ remarks offended many in the audience.",
     ["acerbic", "accolade", "acumen", "acclimate"], 0,
     "'Acerbic' = sharp and forthright in expression; harsh. GRE high-frequency adjective."),
    ("The professor was known for his ___ wit, which often left students bewildered.",
     ["abstruse", "acerbic", "abject", "aberrant"], 1,
     "'Acerbic' = sharp/biting. 'Abstruse' = difficult to understand. Context: wit that confuses."),
    ("The ___ nature of the evidence made it difficult to draw firm conclusions.",
     ["ambiguous", "ambivalent", "ameliorative", "amenable"], 0,
     "'Ambiguous' = open to multiple interpretations. Critical for GRE reading comprehension."),
    ("Despite his ___ reputation, the scholar's latest work was widely praised.",
     ["dubious", "diligent", "didactic", "diffident"], 0,
     "'Dubious' = hesitant or not to be relied upon. Contrast with the positive outcome."),
    ("The author's ___ style made the complex topic accessible to general readers.",
     ["lucid", "laconic", "loquacious", "lugubrious"], 0,
     "'Lucid' = clear and easy to understand. Essential GRE vocabulary for describing writing."),
    ("The committee's decision was seen as ___, ignoring established precedent.",
     ["arbitrary", "arduous", "arcane", "archaic"], 0,
     "'Arbitrary' = based on random choice rather than reason. GRE critical reasoning term."),
    ("The ___ of the argument lay in its failure to account for counterexamples.",
     ["fallacy", "facility", "faculty", "fidelity"], 0,
     "'Fallacy' = a mistaken belief or flawed reasoning. Core GRE analytical writing term."),
    ("The researcher's ___ in the face of repeated failures was admirable.",
     ["tenacity", "temerity", "timidity", "torpor"], 0,
     "'Tenacity' = persistence despite difficulty. 'Temerity' = reckless boldness."),
    ("The critic argued that the novel was ___, rehashing familiar themes without originality.",
     ["derivative", "definitive", "deferential", "desolate"], 0,
     "'Derivative' = imitative of the work of another person; unoriginal."),
    ("The ___ between the two studies made it impossible to compare their results directly.",
     ["discrepancy", "discretion", "discrimination", "dissonance"], 0,
     "'Discrepancy' = a lack of compatibility between facts or claims. GRE data analysis term."),
    ("Her ___ response to the crisis earned her widespread respect.",
     ["judicious", "jocular", "jejune", "jaundiced"], 0,
     "'Judicious' = having or showing good judgment. 'Jejune' = naive or simplistic."),
    ("The theory, once considered ___, has gained renewed attention.",
     ["moribund", "mordant", "morbid", "modest"], 0,
     "'Moribund' = at the point of death; in terminal decline. GRE high-frequency word."),
]

_DRILLS["gre_logic"] = [
    ("The study found a correlation between exercise and longevity; ___, it did not establish causation.",
     ["however", "therefore", "furthermore", "consequently"], 0,
     "'However' signals contrast/concession. Correlation ≠ causation is a key logical distinction."),
    ("The argument assumes that all swans are white; ___, the discovery of black swans refutes it.",
     ["therefore", "nevertheless", "however", "moreover"], 0,
     "'Therefore' introduces a logical conclusion drawn from the preceding premise."),
    ("The policy reduced crime rates in City A; ___, it may not work in City B due to different conditions.",
     ["however", "therefore", "similarly", "consequently"], 0,
     "'However' introduces a limitation or counterargument to the preceding claim."),
    ("The author presents three pieces of evidence; ___, none of them directly supports the main claim.",
     ["nevertheless", "however", "therefore", "furthermore"], 1,
     "'However' = despite what was just said. Signals that the evidence is insufficient."),
    ("The experiment was conducted under controlled conditions; ___, the results are highly reliable.",
     ["therefore", "however", "although", "unless"], 0,
     "'Therefore' = as a logical result. Controlled conditions → reliable results."),
    ("The new drug reduced symptoms in 80% of patients; ___, it caused serious side effects in 20%.",
     ["however", "therefore", "furthermore", "similarly"], 0,
     "'However' introduces a contrasting negative finding after a positive one."),
    ("The first study found no effect; ___, a larger replication study confirmed the original hypothesis.",
     ["however", "therefore", "similarly", "consequently"], 0,
     "'However' signals that the second study contradicts the first."),
    ("The author acknowledges the limitations of the data; ___, she maintains that her conclusions are valid.",
     ["nevertheless", "therefore", "furthermore", "similarly"], 0,
     "'Nevertheless' = in spite of that. Used to maintain a position despite acknowledged weaknesses."),
    ("The evidence is circumstantial; ___, it cannot be used to prove guilt beyond reasonable doubt.",
     ["therefore", "however", "moreover", "nevertheless"], 0,
     "'Therefore' draws a logical conclusion: circumstantial evidence → insufficient for proof."),
    ("The first approach failed due to resource constraints; ___, the team adopted a simpler method.",
     ["consequently", "however", "furthermore", "nevertheless"], 0,
     "'Consequently' = as a result. The failure caused the team to change approach."),
    ("The theory explains most observed phenomena; ___, it fails to account for quantum effects.",
     ["however", "therefore", "furthermore", "consequently"], 0,
     "'However' introduces an exception or limitation to an otherwise strong claim."),
    ("The sample size was small; ___, the findings should be interpreted with caution.",
     ["therefore", "however", "moreover", "similarly"], 0,
     "'Therefore' = logical conclusion. Small sample → cautious interpretation."),
    ("The author claims the policy is cost-effective; ___, she provides no data on implementation costs.",
     ["however", "therefore", "furthermore", "consequently"], 0,
     "'However' signals a gap between the claim and the supporting evidence."),
    ("The first experiment used rats; ___, the second used human subjects.",
     ["in contrast", "therefore", "furthermore", "consequently"], 0,
     "'In contrast' highlights a methodological difference between two studies."),
    ("The data support the hypothesis; ___, the researchers recommend further investigation.",
     ["nevertheless", "however", "therefore", "although"], 2,
     "'Therefore' = as a result. Supporting data → recommendation for further research."),
]

_DRILLS["ielts_cohesion"] = [
    ("___ the high cost of living, many young people cannot afford to buy homes.",
     ["Despite", "Although", "However", "Because"], 0,
     "'Despite' + noun phrase shows contrast. 'Although' needs a full clause."),
    ("The population is aging rapidly. ___, healthcare costs are expected to rise.",
     ["Consequently", "Despite", "Although", "Unless"], 0,
     "'Consequently' = as a result. Links cause (aging) to effect (rising costs)."),
    ("Some people prefer city life; ___, others find rural areas more appealing.",
     ["however", "therefore", "furthermore", "consequently"], 0,
     "'However' contrasts two opposing preferences. Key IELTS cohesive device."),
    ("___ to the government report, air quality has improved significantly.",
     ["According", "Based", "Referring", "Regarding"], 0,
     "'According to' + source is the standard way to cite evidence in IELTS writing."),
    ("The graph shows a steady increase in renewable energy use. ___, fossil fuel consumption has declined.",
     ["Furthermore", "However", "In addition", "Similarly"], 1,
     "'However' signals contrast between two opposing trends in data description."),
    ("Exercise has numerous benefits ___ improved cardiovascular health and reduced stress.",
     ["such as", "for example of", "like as", "including of"], 0,
     "'Such as' introduces examples. 'For example' needs a comma and full sentence."),
    ("The first solution is expensive. The second, ___, is both affordable and effective.",
     ["on the other hand", "in addition", "furthermore", "as a result"], 0,
     "'On the other hand' contrasts two options. Key IELTS Task 2 cohesive device."),
    ("___ the benefits of technology, there are also significant drawbacks.",
     ["In spite of", "Despite", "Alongside", "In addition to"], 3,
     "'In addition to' = as well as. Introduces a contrasting point without dismissing the first."),
    ("The data ___ that urban areas have higher pollution levels than rural ones.",
     ["indicate", "indicates", "is indicating", "indicated"], 1,
     "In IELTS Task 1, use present simple to describe what data shows. 'The data indicates'."),
    ("___ conclusion, the evidence suggests that investment in education yields long-term benefits.",
     ["In", "To", "For", "At"], 0,
     "'In conclusion' is the standard IELTS closing phrase. 'To conclude' is also acceptable."),
    ("The report highlights ___ issues: funding shortages, staff turnover, and poor infrastructure.",
     ["three key", "three keys", "three main of", "three of key"], 0,
     "'Three key issues' = correct noun phrase. No preposition needed between number and noun."),
    ("___ the short term, the policy may reduce costs; however, long-term effects are uncertain.",
     ["In", "For", "At", "On"], 0,
     "'In the short term' / 'in the long term' are fixed IELTS collocations."),
    ("The chart ___ a significant rise in smartphone usage between 2010 and 2020.",
     ["shows", "is showing", "showed", "has shown"], 0,
     "IELTS Task 1: use simple present to describe what a chart/graph shows."),
    ("___ other words, the policy aims to reduce inequality by redistributing wealth.",
     ["In", "With", "By", "For"], 0,
     "'In other words' = to rephrase or clarify. Standard IELTS paraphrasing device."),
    ("The advantages of the scheme ___ the disadvantages.",
     ["outweigh", "outweighs", "are outweighing", "outweighed"], 0,
     "'The advantages outweigh the disadvantages' is a key IELTS Task 2 thesis structure."),
]

_DRILLS["ielts_register"] = [
    ("I think this policy is a bad idea because it will hurt poor people.",
     ["This policy is detrimental as it disproportionately affects low-income groups.",
      "This policy is not good for poor people.",
      "I believe this policy hurts poor people a lot.",
      "The policy is bad and affects poor people."], 0,
     "IELTS requires formal academic register. Avoid 'I think', 'bad', 'hurt' — use formal equivalents."),
    ("Lots of people nowadays use social media all the time.",
     ["A significant proportion of the population engages with social media on a daily basis.",
      "Many people use social media a lot these days.",
      "Nowadays, people use social media very much.",
      "Social media is used by lots of people today."], 0,
     "Replace informal 'lots of', 'all the time', 'nowadays' with formal academic equivalents."),
    ("The government should do something about climate change.",
     ["Governments are obliged to implement measures to address climate change.",
      "The government needs to do things about climate change.",
      "Something should be done by the government about climate change.",
      "The government must fix climate change."], 0,
     "IELTS Band 7+ requires precise, formal vocabulary. 'Implement measures to address' is academic."),
    ("Kids who play video games get worse grades.",
     ["Children who engage in excessive video game use tend to achieve lower academic results.",
      "Kids playing video games have bad grades.",
      "Video games make children's grades go down.",
      "Children who play video games do badly at school."], 0,
     "Replace 'kids', 'get worse', 'grades' with formal equivalents: 'children', 'achieve lower', 'academic results'."),
    ("The ___ of the experiment showed that the drug worked.",
     ["findings", "things found", "found stuff", "results found"], 0,
     "'Findings' is the formal academic noun for results of research. Avoid vague phrases."),
    ("In my opinion, I think that education is very important.",
     ["Education plays a pivotal role in individual and societal development.",
      "I think education is very important.",
      "Education is very important in my opinion.",
      "I believe education matters a lot."], 0,
     "Avoid 'In my opinion, I think' (redundant). Use impersonal academic statements for IELTS."),
    ("The problem got bigger over the years.",
     ["The issue escalated considerably over the course of several years.",
      "The problem became more bigger over the years.",
      "The problem grew more and more over years.",
      "Over the years, the problem got worse and worse."], 0,
     "'Escalated considerably' is formal. Avoid 'got bigger', 'more and more' in academic writing."),
    ("There are good and bad sides to this argument.",
     ["This issue presents both advantages and disadvantages.",
      "This argument has good sides and bad sides.",
      "There are pros and cons to this.",
      "This has both good and bad points."], 0,
     "IELTS formal: 'advantages and disadvantages' or 'merits and drawbacks'. Avoid 'good/bad sides'."),
    ("The graph goes up a lot from 2000 to 2010.",
     ["The graph demonstrates a substantial increase between 2000 and 2010.",
      "The graph increases a lot from 2000 to 2010.",
      "From 2000 to 2010, the graph went up very much.",
      "The graph shows a big rise from 2000 to 2010."], 0,
     "IELTS Task 1: 'demonstrates a substantial increase' is more academic than 'goes up a lot'."),
    ("To sum up, I think both sides have good points.",
     ["In conclusion, both perspectives have considerable merit.",
      "To sum up, both sides are good.",
      "In conclusion, I think both sides are okay.",
      "To conclude, both arguments have good things."], 0,
     "IELTS conclusion: 'In conclusion' + formal language. Avoid 'I think', 'good points'."),
]

_DRILLS["cet_interference"] = [
    ("She ___ very hard to pass the CET-6 exam.",
     ["studied", "learned", "read", "knew"], 0,
     "'Study' = 学习 (systematic effort). 'Learn' = acquire knowledge. 'Read' ≠ study hard. Common Chinese interference: 学 → 'learn' (wrong here)."),
    ("The teacher ___ us a lot of homework every week.",
     ["gave", "sent", "provided", "offered"], 0,
     "'Give homework' is the correct collocation. 'Send homework' is a direct translation error from 布置作业."),
    ("I am looking forward to ___ you soon.",
     ["seeing", "see", "meet", "meeting with"], 0,
     "'Look forward to' + gerund (-ing). Common error: 'look forward to see' (infinitive)."),
    ("The meeting was ___ due to bad weather.",
     ["called off", "called away", "called out", "called up"], 0,
     "'Call off' = cancel. 'Call up' = phone/recruit. Chinese interference: 取消 → 'cancel' or 'call off'."),
    ("He ___ a mistake in his report.",
     ["made", "did", "had", "took"], 0,
     "'Make a mistake' is the fixed collocation. 'Do a mistake' is a direct translation error."),
    ("The experiment ___ three hours to complete.",
     ["took", "spent", "cost", "used"], 0,
     "'It takes time to do something.' 'Spend time doing.' Common error: 'The experiment spent three hours.'"),
    ("She is good ___ mathematics.",
     ["at", "in", "on", "for"], 0,
     "'Good at' + subject/skill. Common Chinese interference: 擅长 → 'good in' (incorrect)."),
    ("The company ___ a new product last month.",
     ["launched", "opened", "started", "began"], 0,
     "'Launch a product' is the correct collocation. 'Open a product' is a translation error from 推出."),
    ("I suggest ___ the meeting to next week.",
     ["postponing", "to postpone", "postpone", "that postpone"], 0,
     "'Suggest' + gerund or 'suggest that + subject + base verb'. 'Suggest to do' is incorrect."),
    ("The news ___ him very happy.",
     ["made", "let", "caused", "had"], 0,
     "'Make someone + adjective' = cause someone to feel. 'Let' = allow. Common error: 'The news let him happy.'"),
    ("She ___ her best to finish the project on time.",
     ["did", "made", "tried", "used"], 0,
     "'Do one's best' is the fixed expression. 'Make one's best' is incorrect."),
    ("The students were asked to ___ their essays by Friday.",
     ["submit", "hand in", "give in", "turn up"], 1,
     "'Hand in' = submit work to a teacher. 'Turn up' = arrive. Both 'submit' and 'hand in' are correct; 'hand in' is more natural in this context."),
    ("He ___ to the library every day to study.",
     ["goes", "walks to", "arrives", "reaches"], 0,
     "'Go to the library' is correct. 'Arrive/reach the library' means getting there, not the habit."),
    ("The price of vegetables ___ a lot recently.",
     ["has risen", "has raised", "raised", "rose up"], 0,
     "'Rise' (intransitive) = go up. 'Raise' (transitive) = lift something. Prices rise; people raise prices."),
    ("I ___ agree with your opinion.",
     ["don't", "not", "no", "am not"], 0,
     "Negation with 'agree': 'I don't agree.' 'I am not agree' is a common Chinese interference error."),
]

_DRILLS["cet_formal"] = [
    ("___ is widely acknowledged that education plays a crucial role in social development.",
     ["It", "There", "This", "That"], 0,
     "'It is widely acknowledged that...' is a formal impersonal structure for CET writing."),
    ("The government has taken ___ measures to address the issue of unemployment.",
     ["effective", "effect", "effecting", "effectively"], 0,
     "'Effective measures' = measures that work. 'Effectively' is an adverb, not an adjective."),
    ("___ the rapid development of technology, traditional industries face new challenges.",
     ["With", "By", "For", "Through"], 0,
     "'With the development of...' is a standard CET writing opening phrase."),
    ("The survey ___ that most students prefer online learning to traditional classroom instruction.",
     ["reveals", "discovers", "finds out", "shows up"], 0,
     "'The survey reveals/shows/indicates that...' are formal reporting verbs for CET writing."),
    ("In recent years, there has been a growing ___ for environmental protection.",
     ["concern", "concerned", "concerning", "concerns"], 0,
     "'A growing concern for' = increasing attention to. Formal noun phrase for CET essays."),
    ("___ conclusion, we should take immediate action to solve this problem.",
     ["In", "To", "For", "At"], 0,
     "'In conclusion' is the standard CET essay closing phrase."),
    ("The ___ of living in big cities has both advantages and disadvantages.",
     ["lifestyle", "life style", "living style", "way to live"], 0,
     "'Lifestyle' (one word) is the correct formal noun. 'Way of living' is also acceptable."),
    ("It is ___ that young people should develop good study habits.",
     ["essential", "essentially", "essence", "essential that"], 0,
     "'It is essential that + subject + base verb' (subjunctive). 'It is essential' + infinitive also works."),
    ("The ___ between urban and rural areas remains a significant challenge.",
     ["gap", "difference of", "distance", "distinction of"], 0,
     "'The gap between X and Y' is a formal CET phrase for describing inequality or disparity."),
    ("___ order to improve English proficiency, students should read extensively.",
     ["In", "For", "With", "By"], 0,
     "'In order to' + infinitive expresses purpose. More formal than 'to' alone."),
    ("The rapid ___ of the internet has transformed the way people communicate.",
     ["development", "develop", "developing", "developed"], 0,
     "'The development of' + noun is a standard CET academic phrase."),
    ("She worked ___ to achieve her academic goals.",
     ["diligently", "diligent", "with diligence of", "in a diligent"], 0,
     "Adverb 'diligently' modifies the verb 'worked'. Formal alternative to 'hard'."),
    ("The ___ of this essay is to analyze the causes of air pollution.",
     ["purpose", "aim", "objective", "intention"], 0,
     "All four are correct, but 'purpose' is most common in CET essay introductions."),
    ("___ the advantages mentioned above, there are also some disadvantages.",
     ["Despite", "Besides", "Although", "However"], 1,
     "'Besides' = in addition to. 'Despite' = in spite of. Context: adding disadvantages to advantages."),
    ("The problem of food waste ___ immediate attention from both individuals and governments.",
     ["requires", "needs", "demands", "calls"], 2,
     "'Demand immediate attention' is a strong formal collocation. 'Require' and 'need' also work."),
]

_SKILL_MAP = {
    "articles": "grammar_articles",
    "prepositions": "grammar_preposition",
    "tense": "grammar_tense",
    "subject_verb": "grammar_tense",
    "passive": "grammar_tense",
    "toefl_academic": "grammar_tense",
    "toefl_structure": "grammar_tense",
    "gre_verbal": "grammar_tense",
    "gre_logic": "grammar_tense",
    "ielts_cohesion": "grammar_tense",
    "ielts_register": "grammar_tense",
    "cet_interference": "grammar_tense",
    "cet_formal": "grammar_tense",
}

# Exam-specific category metadata
_EXAM_CATEGORIES: dict[str, list[str]] = {
    "toefl": ["toefl_academic", "toefl_structure"],
    "gre":   ["gre_verbal", "gre_logic"],
    "ielts": ["ielts_cohesion", "ielts_register"],
    "cet":   ["cet_interference", "cet_formal"],
    "general": [],
}

_CATEGORY_LABELS: dict[str, str] = {
    "articles":         "Articles",
    "prepositions":     "Prepositions",
    "tense":            "Verb Tense",
    "subject_verb":     "Subject-Verb Agreement",
    "passive":          "Passive Voice",
    "toefl_academic":   "TOEFL Academic Vocabulary",
    "toefl_structure":  "TOEFL Sentence Structure",
    "gre_verbal":       "GRE Verbal Reasoning",
    "gre_logic":        "GRE Logical Connectors",
    "ielts_cohesion":   "IELTS Cohesive Devices",
    "ielts_register":   "IELTS Academic Register",
    "cet_interference": "CET Chinese-English Patterns",
    "cet_formal":       "CET Formal Writing",
}


def run_grammar_session(
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    focus: Optional[str] = None,
    num_questions: int = 10,
) -> dict:
    """
    Run a grammar drill session.
    - Picks drills based on user's weak areas or specified focus
    - Multiple-choice format, instant feedback
    - Optional AI explanation for wrong answers
    """
    session_id = user_model.start_session(profile.user_id, "grammar")
    start_time = time.time()

    print_header(
        "语法练习  ·  Grammar Drills",
        subtitle=f"CEFR {profile.cefr_level}",
    )

    # Pick focus area
    category = _pick_category(focus, user_model, profile)
    drills = _DRILLS.get(category, [])
    if not drills:
        console.print(f"[yellow]No drills found for category: {category}[/yellow]")
        return {}

    console.print(f"\n[bold]Focus:[/bold] [cyan]{category.replace('_', ' ').title()}[/cyan]  "
                  f"({len(drills)} questions available)\n")

    # Sample questions
    selected = random.sample(drills, min(num_questions, len(drills)))
    stats = {"correct": 0, "total": len(selected), "wrong": []}

    for i, (sentence, choices, correct_idx, explanation) in enumerate(selected, 1):
        result = _ask_drill(i, len(selected), sentence, choices, correct_idx, explanation)
        if result:
            stats["correct"] += 1
            user_model.record_answer(profile.user_id, _SKILL_MAP.get(category, "grammar_tense"), True)
        else:
            stats["wrong"].append((sentence, choices[correct_idx], explanation))
            user_model.record_answer(profile.user_id, _SKILL_MAP.get(category, "grammar_tense"), False)

            # Optional AI explanation for wrong answers
            if ai and len(stats["wrong"]) <= 2:
                _show_ai_explanation(ai, sentence, choices[correct_idx], profile.cefr_level)

    # Summary
    duration = int(time.time() - start_time)
    accuracy = stats["correct"] / stats["total"]
    user_model.end_session(session_id, duration, stats["total"], accuracy)
    user_model.update_profile(profile)

    print_session_summary(
        mode="Grammar",
        reviewed=stats["total"],
        correct=stats["correct"],
        duration_sec=duration,
    )

    if stats["wrong"]:
        console.print("\n[bold yellow]Review these patterns:[/bold yellow]")
        for sentence, answer, expl in stats["wrong"][:3]:
            console.print(f"  [yellow]→[/yellow] {sentence}")
            console.print(f"    [green]Correct: {answer}[/green]")
            console.print(f"    [dim]{expl[:100]}...[/dim]\n")

    return stats


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _pick_category(focus: Optional[str], user_model: UserModel, profile: UserProfile) -> str:
    """Pick drill category: explicit focus > weak area > random."""
    if focus and focus in _DRILLS:
        return focus

    # Check weak areas
    scores = user_model.get_skill_scores(profile.user_id)
    grammar_skills = {
        "grammar_articles": "articles",
        "grammar_preposition": "prepositions",
        "grammar_tense": "tense",
    }
    weakest = None
    weakest_score = 1.0
    for skill, category in grammar_skills.items():
        score = scores.get(skill, 0.5)
        if score < weakest_score:
            weakest_score = score
            weakest = category

    return weakest or random.choice(list(_DRILLS.keys()))


def _ask_drill(
    num: int,
    total: int,
    sentence: str,
    choices: list[str],
    correct_idx: int,
    explanation: str,
) -> bool:
    """Display one fill-in-the-blank drill. Returns True if correct."""
    console.print(f"[bold cyan]Q{num}/{total}[/bold cyan]  {sentence}\n")

    for i, choice in enumerate(choices, 1):
        console.print(f"  [dim]{i}.[/dim] {choice}")

    answer = Prompt.ask(
        "\n  Your answer",
        choices=[str(i) for i in range(1, len(choices) + 1)],
        default="1",
    )
    chosen_idx = int(answer) - 1
    correct = chosen_idx == correct_idx

    if correct:
        console.print(f"\n  [green]✓ Correct![/green]  {explanation}\n")
    else:
        console.print(
            f"\n  [red]✗ Incorrect.[/red]  "
            f"Correct answer: [green]{choices[correct_idx]}[/green]\n"
            f"  [dim]{explanation}[/dim]\n"
        )

    return correct


def _show_ai_explanation(
    ai: AIClient,
    sentence: str,
    correction: str,
    cefr_level: str,
) -> None:
    """Show an AI-generated grammar explanation (cached)."""
    with console.status("[dim]Getting deeper explanation...[/dim]"):
        explanation = ai.explain_grammar(
            error_sentence=sentence,
            correction=correction,
            cefr_level=cefr_level,
        )
    console.print(Panel(
        explanation,
        title="[dim]AI Explanation[/dim]",
        border_style="dim",
        padding=(0, 2),
    ))
