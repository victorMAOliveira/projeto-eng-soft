--[[
Pandoc filter for the report (used by scripts/render_pandoc.sh).

Keeps relatorio.md as plain, portable Markdown (it renders cleanly on GitHub
and in editors) and adds the output-specific pieces at build time:

* DOCX: after the cover (<div class="capa">) insert a page break, the
  "Sumário" heading, a Word table-of-contents field (filled when the document
  is opened) and another page break.
* Every format: headings that start with "Parte " (e.g. "Parte 1 — Modelagem")
  get the class "parte", styled as a divider page in style.css.
]]

local TOC_XML = table.concat({
  '<w:p><w:r><w:br w:type="page"/></w:r></w:p>',
  '<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Sumário</w:t></w:r></w:p>',
  '<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/>',
  '<w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent><w:p>',
  '<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>',
  '<w:r><w:instrText xml:space="preserve">TOC \\o "1-2" \\h \\z \\u</w:instrText></w:r>',
  '<w:r><w:fldChar w:fldCharType="separate"/></w:r>',
  '<w:r><w:t>Clique com o botão direito e escolha "Atualizar campo" para gerar o sumário.</w:t></w:r>',
  '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:sdtContent></w:sdt>',
  '<w:p><w:r><w:br w:type="page"/></w:r></w:p>',
})

function Header(el)
  if pandoc.utils.stringify(el.content):match("^Parte ") then
    el.classes:insert("parte")
  end
  return el
end

function Pandoc(doc)
  if FORMAT ~= "docx" then
    return doc
  end
  local blocks = {}
  for _, block in ipairs(doc.blocks) do
    blocks[#blocks + 1] = block
    if block.t == "Div" and block.classes:includes("capa") then
      blocks[#blocks + 1] = pandoc.RawBlock("openxml", TOC_XML)
    end
  end
  doc.blocks = blocks
  return doc
end
