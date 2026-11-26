# Instruções para Agentes - writing_guard

Ao interagir, modificar ou adicionar termos às regras e bases de dados desta ferramenta (`writing_guard`):

1. **Verificação Prévia Obrigatória:**
   - Antes de adicionar qualquer palavra ou termo novo aos ficheiros de regras (`writing_guard/rules/ai_isms.json`, `writing_guard/rules/pt_br_lexicon.json`) ou à lista de exceções (`writing_guard/whitelist.txt`), **deve ser sempre verificado primeiro se o termo (ou variantes/formas flexionadas) já existe na base de dados**.
   - Para verificar nos ficheiros de regras: procure pelo termo exato e respetivos plurais/formas flexionadas em `writing_guard/rules/ai_isms.json` e `writing_guard/rules/pt_br_lexicon.json`.
   - Se a palavra já constar da base de dados, não a duplique; verifique antes se a explicação ou as sugestões existentes precisam de refinamento ou complemento.

2. **Consistência de Regras:**
   - Ao adicionar substantivos ou adjetivos, inclua tanto a forma no singular como no plural (e masculino/feminino quando relevante).
   - Em `writing_guard/rules/ai_isms.json`, mantenha sempre os campos `"suggestion"` e `"explanation"` claros, contextualizados para português europeu (`pt-PT`) formal/técnico e indicando a origem do decalque (ex.: inglês).
   - Valide sempre que a sintaxe JSON permanece válida após qualquer edição.
