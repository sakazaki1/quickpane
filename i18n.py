"""Small system-locale based translations for QuickPane's interface."""

from PyQt6.QtCore import QLocale


TRANSLATIONS = {
    "Pronto": "Ready",
    "Conversa": "Chat",
    "Relatórios": "Reports",
    "Ações e atalhos": "Actions and shortcuts",
    "Chat rápido": "Quick chat",
    "+ Novo chat": "+ New chat",
    "Nova conversa sem o contexto anterior · Ctrl+N": "Start a clean chat · Ctrl+N",
    "Expandir ou reduzir": "Expand or collapse",
    "Ocultar": "Hide",
    "Sair": "Quit",
    "Abrir ou ocultar": "Show or hide",
    "Capturar print": "Capture screenshot",
    "Seu painel de acesso rápido": "Your quick access panel",
    "Continuar com ChatGPT": "Continue with ChatGPT",
    "Aguardando autorização no navegador...": "Waiting for browser authorization...",
    "Conta conectada": "Account connected",
    "Modelo · conecte sua conta": "Model · connect your account",
    "Envie uma mensagem ou um print": "Send a message or screenshot",
    "↶  Último chat": "↶  Previous chat",
    "Reabrir a conversa anterior desta sessão": "Reopen the previous chat from this session",
    "⧉  Copiar resposta": "⧉  Copy answer",
    "Copiar a última resposta · Ctrl+Shift+C": "Copy the latest answer · Ctrl+Shift+C",
    "Print anexado": "Screenshot attached",
    "Remover print": "Remove screenshot",
    "▣   Cole um print ou clique para capturar": "▣   Paste a screenshot or click to capture",
    "Anexar imagem": "Attach image",
    "Capturar uma área": "Capture a region",
    "Enviar · Ctrl+Enter": "Send · Ctrl+Enter",
    "Digite ou cole um print...": "Type or paste a screenshot...",
    "Envie texto ou print": "Send text or a screenshot",
    "Capture a tela ou escreva sua pergunta. A resposta aparece aqui enquanto é gerada.": "Capture the screen or type your question. The answer appears here as it is generated.",
    "Conecte sua conta ChatGPT para enviar.": "Connect your ChatGPT account to send a message.",
    "Selecione um modelo antes de enviar.": "Select a model before sending.",
    "Não foi possível carregar os modelos: ": "Could not load models: ",
    "Aguarde a lista de modelos ou selecione um modelo.": "Wait for the model list or select a model.",
    "Print anexado": "Screenshot attached",
    "Preparando sua resposta": "Preparing your response",
    "Resposta pronta": "Response ready",
    "Não foi possível concluir": "Could not complete",
    "Não foi possível concluir: ": "Could not complete: ",
    "Aguarde esta resposta para iniciar outra conversa": "Wait for this response to finish before starting another chat",
    "Novo chat sem contexto anterior": "New chat with no previous context",
    "Novo chat após período de inatividade": "New chat after inactivity",
    "Conversa anterior reaberta": "Previous chat reopened",
    "Resposta copiada": "Answer copied",
    "Executando...": "Working...",
    "Concluído": "Completed",
    "Erro": "Error",
    "Ativo": "Active",
    "Feito": "Done",
    "Pronto para começar": "Ready to start",
    "Você": "You",
    "Ações": "Actions",
    "Novo chat   Ctrl+N": "New chat   Ctrl+N",
    "Reabrir último chat": "Reopen previous chat",
    "Copiar resposta   Ctrl+Shift+C": "Copy answer   Ctrl+Shift+C",
    "Novo chat após inatividade": "New chat after inactivity",
    "5 minutos": "5 minutes",
    "15 minutos": "15 minutes",
    "30 minutos": "30 minutes",
    "Nunca": "Never",
    "Capturar área": "Capture region",
    "Atalhos": "Shortcuts",
    "Ctrl+V   Colar print": "Ctrl+V   Paste screenshot",
    "Ctrl+Enter   Enviar": "Ctrl+Enter   Send",
    "Esc   Ocultar janela": "Esc   Hide window",
    "Anexar print": "Attach screenshot",
    "Imagens (*.png *.jpg *.jpeg *.webp)": "Images (*.png *.jpg *.jpeg *.webp)",
    "Esta imagem não pôde ser aberta.": "This image could not be opened.",
    "Captura cancelada ou indisponível. Use Ctrl+V para colar um print.": "Capture cancelled or unavailable. Use Ctrl+V to paste a screenshot.",
    "Não foi possível abrir o print capturado.": "Could not open the captured screenshot.",
    "O Spectacle não está instalado. Cole um print com Ctrl+V.": "Spectacle is not installed. Paste a screenshot with Ctrl+V.",
    "Nenhum modelo disponível para esta conta.": "No models are available for this account.",
    "O login expirou. Tente novamente.": "Sign-in expired. Please try again.",
    "O retorno do login não passou pela validação de segurança.": "The sign-in response did not pass security validation.",
    "A autorização foi cancelada ou recusada.": "Authorization was cancelled or denied.",
    "Não foi possível validar o registro do aplicativo.": "Could not validate the application registration.",
    "O login não retornou um código de autorização.": "Sign-in did not return an authorization code.",
    "O uso do plano ChatGPT não foi autorizado para este aplicativo.": "ChatGPT plan access was not authorized for this application.",
    "O login retornou um nonce inválido.": "Sign-in returned an invalid nonce.",
    "A conta retornada é diferente da conta salva.": "The returned account differs from the saved account.",
    "Conta ChatGPT": "ChatGPT account",
    "Conecte sua conta ChatGPT primeiro.": "Connect your ChatGPT account first.",
    "A resposta falhou.": "The response failed.",
    "Falha na conexão.": "Connection failed.",
    "A conexão terminou sem confirmar a conclusão da resposta.": "The connection ended before confirming the response was complete.",
}


def system_language(system_name: str | None = None) -> str:
    """Return ``pt`` for Portuguese system locales and ``en`` otherwise."""
    locale_name = (system_name or QLocale.system().name()).replace("-", "_").lower()
    return "pt" if locale_name.startswith("pt_") or locale_name == "pt" else "en"


def tr(text: str, language: str | None = None) -> str:
    language = language or system_language()
    if language == "pt":
        return text
    for prefix in ("Não foi possível carregar os modelos: ", "Não foi possível concluir: "):
        if text.startswith(prefix):
            return TRANSLATIONS[prefix] + tr(text[len(prefix):], language)
    return TRANSLATIONS.get(text, text)
