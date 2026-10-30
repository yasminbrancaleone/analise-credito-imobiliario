from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


OUT = "output/pdf/resumo_executivo.pdf"
NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#236B9B")
LIGHT_BLUE = colors.HexColor("#EAF3F8")
GRAY = colors.HexColor("#5B6770")
LIGHT_GREEN = colors.HexColor("#EAF7F0")
LIGHT_ORANGE = colors.HexColor("#FFF3E6")


styles = getSampleStyleSheet()
styles.add(ParagraphStyle("TitleCustom", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19, leading=21, textColor=NAVY, spaceAfter=1))
styles.add(ParagraphStyle("Subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=12, textColor=GRAY, spaceAfter=3))
styles.add(ParagraphStyle("Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=12, textColor=BLUE, spaceBefore=4, spaceAfter=3))
styles.add(ParagraphStyle("BodySmall", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.4, leading=9.1, textColor=colors.HexColor("#222222"), spaceAfter=2))
styles.add(ParagraphStyle("BodySmallCenter", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.1, leading=8.2, alignment=TA_CENTER, textColor=GRAY))
styles.add(ParagraphStyle("KpiValue", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=13.5, leading=15, alignment=TA_CENTER, textColor=NAVY))
styles.add(ParagraphStyle("KpiLabel", parent=styles["BodyText"], fontName="Helvetica", fontSize=6.6, leading=7.5, alignment=TA_CENTER, textColor=GRAY))
styles.add(ParagraphStyle("Table", parent=styles["BodyText"], fontName="Helvetica", fontSize=6.9, leading=8.1, textColor=colors.HexColor("#222222")))
styles.add(ParagraphStyle("TableBold", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=6.9, leading=8.1, textColor=NAVY))
styles.add(ParagraphStyle("Foot", parent=styles["BodyText"], fontName="Helvetica", fontSize=6.3, leading=7.2, textColor=GRAY))


def p(text, style="BodySmall"):
    return Paragraph(text, styles[style])


def section(title):
    return [Spacer(1, 2), Paragraph(title, styles["Section"]), Table([['']], colWidths=[17.9 * cm], rowHeights=[0.5], style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE), ("LINEBELOW", (0, 0), (-1, -1), 0, BLUE)])), Spacer(1, 2)]


doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=1.35 * cm, rightMargin=1.35 * cm, topMargin=1.1 * cm, bottomMargin=1.0 * cm)
doc.addPageTemplates([PageTemplate(id="one", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")])])
story = []

story.append(Paragraph("Diagnóstico do Funil de Crédito", styles["TitleCustom"]))
story.append(Paragraph("Resumo executivo para decisão comercial", styles["Subtitle"]))
story.append(Paragraph("Base sintética com 6.400 propostas. A análise considera a última etapa alcançada por cada proposta.", styles["Foot"]))
story.append(Spacer(1, 4))

kpis = [
    [p("5.865", "KpiValue"), p("19,2%", "KpiValue"), p("R$ 416,5 mi", "KpiValue"), p("R$ 1,84 bi", "KpiValue")],
    [p("propostas após limpeza", "KpiLabel"), p("conversão geral", "KpiLabel"), p("valor contratado", "KpiLabel"), p("valor potencial não convertido", "KpiLabel")],
]
kpi_table = Table(kpis, colWidths=[4.47 * cm] * 4, rowHeights=[0.62 * cm, 0.46 * cm])
kpi_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.4, colors.white), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.white), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
story.append(kpi_table)

story += section("Mensagem principal")
story.append(p("O funil não mostra uma queda acentuada de conversão no período: a taxa média passou de 19,80% na primeira metade para 18,64% na segunda, uma variação de -1,16 ponto percentual. A hipótese sobre os Correspondentes merece investigação: o canal converteu 13,7%, contra aproximadamente 21,4% nos demais, diferença estatisticamente significativa no teste qui-quadrado (p < 0,001), mas sem evidência de causalidade."))

story += section("Onde está a maior oportunidade financeira?")
rows = [[p("Última etapa alcançada", "TableBold"), p("Propostas", "TableBold"), p("Valor solicitado", "TableBold")], [p("Análise de Crédito"), p("1.657"), p("R$ 649,8 mi")], [p("Avaliação do Imóvel"), p("1.151"), p("R$ 453,8 mi")], [p("Formalização"), p("764"), p("R$ 296,1 mi")], [p("Lead"), p("909"), p("R$ 346,8 mi")], [p("Simulação"), p("256"), p("R$ 97,9 mi")]]
stage_table = Table(rows, colWidths=[10.4 * cm, 2.5 * cm, 5.0 * cm])
stage_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE), ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 0.4, BLUE), ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#D8E0E6")), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
story.append(stage_table)
story.append(p("A Análise de Crédito concentra o maior valor entre as propostas que não chegaram à contratação. O valor potencial perdido é um teto de oportunidade: não significa que todo esse montante seria aprovado ou contratado.", "Foot"))

story += section("Achados que orientam a ação")
story.append(p("<b>Política de LTV:</b> 904 propostas (15,4% da base limpa) ficaram acima de 60%. Houve 109 contratos nessa faixa. Isso indica exceções ou critérios adicionais que precisam ser entendidos, não uma regra automática de descarte."))
story.append(p("<b>Perfil associado à contratação:</b> LTV dentro da política, score mais alto e alguns tipos de imóvel apresentam taxas maiores. São associações para priorização e investigação, não regras de causalidade."))
story.append(p("<b>Qualidade dos dados:</b> 535 Terrenos foram removidos conforme o dicionário; três datas inválidas viraram NaT; três valores com prefixo R$ foram corrigidos; uma etapa 7 foi mantida na base, mas retirada do funil."))

story += section("Recomendações priorizadas")
rec_rows = [[p("Prior.", "TableBold"), p("Ação", "TableBold"), p("Por que agora", "TableBold")], [p("1", "TableBold"), p("Investigar a operação dos Correspondentes: origem, triagem, documentação e perfil das propostas."), p("Conversão de 13,7% e diferença de cerca de 7,6 pp; o impacto estimado depende de controlar a composição dos leads.")], [p("2", "TableBold"), p("Criar uma triagem específica para LTV acima de 60% e priorizar a faixa de 50% a 60%."), p("904 propostas estão acima da política, mas 109 contratos mostram que há exceções reais.")], [p("3", "TableBold"), p("Mapear a passagem pela Análise de Crédito e os principais motivos de abandono."), p("É a etapa com maior valor associado às propostas que não avançaram: R$ 649,8 milhões.")]]
rec_table = Table(rec_rows, colWidths=[1.0 * cm, 8.4 * cm, 8.5 * cm])
rec_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT_GREEN), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.HexColor("#21865B")), ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#CFE5D9")), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
story.append(rec_table)

story += section("Limites para a decisão")
story.append(p("Os dados são sintéticos e a análise é local. As coortes dos dois meses mais recentes podem estar incompletas, portanto a comparação temporal deve ser repetida com uma janela de maturação definida pelo negócio. A Parte 3 usa modelo de linguagem para extrair 10 campos dos 17 laudos; Pydantic valida estrutura e tipos, enquanto evidências e golden dataset ajudam a medir a qualidade. Conflitos ainda podem exigir revisão humana."))

callout = Table([[p("<b>Próxima decisão sugerida:</b> definir a janela de maturação das propostas e solicitar ao canal Correspondentes um recorte de perfil e motivos de abandono antes de alterar metas ou política.")]], colWidths=[17.9 * cm])
callout.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_ORANGE), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E67E22")), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
story.append(callout)
story.append(Spacer(1, 3))
story.append(p("Fonte: propostas_credito.csv, 17 laudos e golden dataset fornecidos. Associação não implica causalidade.", "Foot"))

doc.build(story)
