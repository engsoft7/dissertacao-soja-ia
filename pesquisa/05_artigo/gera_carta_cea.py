# -*- coding: utf-8 -*-
"""Cover letter da submissão à Smart Agricultural Technology.

A versão anterior desta carta acompanhou a submissão à Computers and
Electronics in Agriculture, recusada em 12/09/2026 com três objeções de
mérito. Esta declara a recusa e o que mudou: esconder uma avaliação anterior
de um editor que pode consultá-la no mesmo sistema seria tão inútil quanto
desonesto, e declarar reforça o que há de melhor no manuscrito — que as três
objeções foram respondidas com análise nova, e uma delas contra a expectativa
dos próprios autores.
"""
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH as AL
from docx.shared import Cm, Pt

RAIZ = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(RAIZ, 'saida')
os.makedirs(SAIDA, exist_ok=True)

F = 'Times New Roman'
d = Document()
s = d.sections[0]
s.page_width, s.page_height = Cm(21.0), Cm(29.7)
s.top_margin = s.bottom_margin = Cm(2.5)
s.left_margin = s.right_margin = Cm(2.5)
d.styles['Normal'].font.name = F
d.styles['Normal'].font.size = Pt(11)


def p(t='', neg=False, align=AL.JUSTIFY, dep=10, lh=1.15):
    par = d.add_paragraph()
    par.alignment = align
    par.paragraph_format.line_spacing = lh
    par.paragraph_format.space_after = Pt(dep)
    if t:
        r = par.add_run(t)
        r.font.name, r.font.size, r.font.bold = F, Pt(11), neg
    return par


p('Maycon Lima dos Santos', align=AL.LEFT, dep=0)
p('Graduate Program in Applied Computing (PPCA)', align=AL.LEFT, dep=0)
p('Universidade Federal do Pará — Tucuruí, PA, Brazil', align=AL.LEFT, dep=0)
p('ORCID 0009-0005-9424-6048 — mayconlimasan@gmail.com', align=AL.LEFT, dep=16)

p('14 September 2026', align=AL.LEFT, dep=16)

p('To the Editors-in-Chief', align=AL.LEFT, dep=0)
p('Smart Agricultural Technology', align=AL.LEFT, dep=16)

p('Dear Editors,')

p('I submit for your consideration the manuscript "Value repetition in official crop '
  'statistics: a diagnostic of target-variable quality and its effect on the '
  'evaluation of machine learning yield models", as a research paper.')

p('The manuscript was previously submitted to Computers and Electronics in '
  'Agriculture (COMPAG-D-26-09128) and rejected on 12 September 2026 after review. I '
  'declare this at the outset, and summarise below what the reviewers objected to and '
  'what has changed, so that you may judge the work with that history in view.')

p('Machine learning for crop yield prediction is evaluated against official '
  'statistics taken as ground truth. The systematic reviews that map the field do not '
  'offer a way to check whether the target variable carries the interannual variation '
  'the model is asked to predict. This manuscript proposes one — the rate at which '
  'consecutive values repeat — and applies it to the Brazilian Municipal Agricultural '
  'Production survey for soybean, across 2,806 municipalities and 24 crop years. Of '
  '46,536 consecutive-season pairs, 17.6% report strictly identical yield, and what '
  'predicts the rate is not the region but the scale of the crop in the municipality.')

p('The reviewers raised three objections. Each has been answered with new analysis, '
  'and one of the answers contradicted what I expected to find.')

p('First, that the permutation null ignored temporal dependence. It did, and the '
  'objection was correct: shuffling a yield series destroys the trend and persistence '
  'that make adjacent seasons resemble each other. The manuscript now tests against '
  'surrogates that preserve both the autocorrelation and the exact value repertoire. '
  'A surrogate reproducing the observed lag-1 autocorrelation expects 10.6% '
  'repetition; one made deliberately smoother than the data expects 12.5%; the '
  'observation is 17.5%. The length of the constant runs settles it — 694 runs of '
  'four or more seasons at one value against 260 expected, and one run of seventeen.')

p('Second, that comparable performance between algorithms and a historical baseline '
  'does not isolate the effect of target quality. Also correct. The manuscript now '
  'reports an injection experiment in which every predictor is held fixed and only '
  'the target is corrupted, by carrying previous values forward in a growing fraction '
  'of records. The result is not the one I predicted. True predictive performance does '
  'not degrade. What happens instead is that apparent performance rises — 37% for a '
  'history-only baseline, 80% for the environmental model — while the measured gap '
  'between the two collapses from −0.052 to −0.001. Repetition does not bound '
  'predictive skill; it removes the ability to measure it, while inflating the figure '
  'that would be reported. The manuscript\'s earlier claim of a performance ceiling '
  'has been withdrawn, and the title changed accordingly.')

p('Third, that independent validation of the diagnostic was insufficient. The '
  'manuscript now draws it from the survey itself, which publishes planted area '
  'alongside yield in a separate field. Planted area repeats together with yield in '
  '44.3% of repeated pairs against 19.3% otherwise; and where yield repeats while '
  'area moves, area moves by a median of 25.0% against 8.9%. A municipality whose '
  'soybean area grew by half and which reports the same yield to the kilogram implies '
  'a production that followed area in exact proportion — a coincidence that would '
  'have to recur thousands of times. A second, orbital check was attempted in the '
  'Pará dataset and did not succeed; it is reported as a null result, because it '
  'bounds what the diagnostic has been shown to do.')

p('On the fit to your scope: the manuscript proposes no new algorithm and uses '
  'established implementations. Its contribution is to the machine learning pipeline '
  'rather than to agronomy — a diagnostic computed from the target series alone, '
  'before any model is fitted, costing a single pass over the data, which identifies '
  'datasets on which model comparison cannot be informative. Given that apparent '
  'accuracy rises with repetition, the studies most exposed are not those reporting '
  'poor results but those reporting comfortable ones.')

p('The dataset assembled for this study — 49,342 municipality-season records from the '
  'primary source, together with the derived measures and every analysis script, '
  'including those written to answer the objections above — is openly archived at '
  'Zenodo under DOI 10.5281/zenodo.22739059, the version cited in the manuscript, '
  'and available at '
  'https://github.com/engsoft7/dissertacao-soja-ia. Every numerical claim in the '
  'manuscript can be recomputed from that deposit.')

p('The work is original and is not under consideration by any other journal. It is '
  'single-authored. Part of the Pará case study derives from my master\'s dissertation '
  'at the Universidade Federal do Pará; the national analysis that forms the core of '
  'this manuscript is new and was not part of that work. I declare no competing '
  'interests. The use of generative AI in manuscript preparation is declared in the '
  'manuscript, as required by Elsevier policy.')

p('I thank you for your time and look forward to your response.')

p('Sincerely,', dep=16)
p('Maycon Lima dos Santos', align=AL.LEFT, dep=0)
p('Graduate Program in Applied Computing, Universidade Federal do Pará', align=AL.LEFT,
  dep=0)

d.save(os.path.join(SAIDA, 'Cover_letter.docx'))
print('gerada')
