#!/bin/bash
# Monitor de testes em tempo real - mostra logs formatados

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}🔍 MONITOR DE TESTES - Tool Calling${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Monitorando logs em tempo real...${NC}"
echo -e "${YELLOW}Pressione Ctrl+C para parar${NC}"
echo ""

# Function to extract and format logs
format_log() {
    while IFS= read -r line; do
        # Extract event type
        if echo "$line" | grep -q "llm_response_generated"; then
            cost=$(echo "$line" | grep -oP '"cost_usd":\s*\K[0-9.]+' || echo "0")
            input_tokens=$(echo "$line" | grep -oP '"input_tokens":\s*\K[0-9]+' || echo "0")
            output_tokens=$(echo "$line" | grep -oP '"output_tokens":\s*\K[0-9]+' || echo "0")
            provider=$(echo "$line" | grep -oP '"provider_used":\s*"\K[^"]+' || echo "unknown")

            echo -e "${GREEN}💰 LLM Response:${NC} Cost=\$$cost | In=$input_tokens | Out=$output_tokens | Provider=$provider"

        elif echo "$line" | grep -q "\"event\".*\"tool"; then
            tool_name=$(echo "$line" | grep -oP '"tool_name":\s*"\K[^"]+' || echo "unknown")

            echo -e "${BLUE}🛠️  Tool Called:${NC} $tool_name"

        elif echo "$line" | grep -q "node_error"; then
            node=$(echo "$line" | grep -oP '"node":\s*"\K[^"]+' || echo "unknown")
            error=$(echo "$line" | grep -oP '"error_type":\s*"\K[^"]+' || echo "unknown")

            echo -e "${RED}❌ Error:${NC} Node=$node | Type=$error"

        elif echo "$line" | grep -q "rate_limit"; then
            echo -e "${YELLOW}⚠️  Rate Limit${NC}"
        fi
    done
}

# Monitor logs
if [ -f "logs/app.log" ]; then
    echo -e "${CYAN}Lendo logs de: logs/app.log${NC}"
    echo ""
    tail -f logs/app.log | format_log
else
    echo -e "${YELLOW}⚠️  Arquivo logs/app.log não encontrado${NC}"
    echo -e "${YELLOW}Os logs serão exibidos no stdout durante o teste${NC}"
    echo ""
    echo -e "${CYAN}Aguardando logs...${NC}"

    # Wait for log file to be created
    while [ ! -f "logs/app.log" ]; do
        sleep 1
    done

    echo -e "${GREEN}✅ Log file criado!${NC}"
    echo ""
    tail -f logs/app.log | format_log
fi
