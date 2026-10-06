# Como Contribuir para Código Vivo

## 🎯 Diretrizes de Contribuição

Obrigado por considerar contribuir para o Código Vivo! Este documento fornece orientações e instruções para você contribuir com o projeto.

## 📋 Código de Conduta

Esperamos que todos os contribuidores sigam nosso Código de Conduta:
- Seja respeitoso
- Seja inclusivo
- Seja profissional
- Rejeite discriminação

## 🔄 Processo de Contribuição

### 1. Crie uma Issue

Antes de começar a trabalhar, crie uma issue descrevendo:
- O problema que você quer resolver
- A solução proposta
- Qualquer contexto adicional

### 2. Fork e Clone

```bash
git clone https://github.com/leoolivramos/darwin.git
cd darwin
git checkout -b feature/sua-feature
```

### 3. Desenvolvimento

```bash
# Crie um ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instale dependências
pip install -r requirements-dev.txt

# Desenvolva sua feature
# Faça commits frequentes e com mensagens descritivas
git commit -m "feat: descrição clara da mudança"
```

### 4. Testes

```bash
# Execute testes localmente
pytest tests/unit -v
pytest tests/integration -v

# Verifique cobertura
pytest --cov=src tests/
```

### 5. Code Quality

```bash
# Lint
flake8 src/ tests/
black --check src/ tests/

# Type checking
mypy src/

# Security
bandit -r src/
```

### 6. Merge Request

- Abra um Merge Request com:
  - Descrição clara das mudanças
  - Link para a issue relacionada
  - Screenshots se aplicável
  - Resultados de testes

### 7. Review

Um mantenedor irá revisar e solicitar mudanças se necessário.

## 🏗️ Diretrizes de Código

### Python

```python
# Use type hints
def detect_hotspots(metrics: Dict[str, float]) -> List[Hotspot]:
    pass

# Docstrings
def query_prometheus(query: str) -> Dict[str, Any]:
    """
    Execute a PromQL query against Prometheus.
    
    Args:
        query: PromQL query string
        
    Returns:
        Response data from Prometheus
        
    Raises:
        PrometheusError: If query fails
    """
    pass

# Use logging
logger.info("Hotspot detected", extra={
    "endpoint": "/api/users",
    "metric": "latency_p99"
})
```

### Java/Spring Boot

```java
// Use Spring Best Practices
@RestController
@RequestMapping("/api")
public class UserController {
    
    private static final Logger logger = LoggerFactory.getLogger(UserController.class);
    
    @GetMapping("/users")
    @Timed(value = "http.requests.duration", description = "Request duration")
    public ResponseEntity<List<User>> getUsers() {
        // Implementation
    }
}

// Add metrics
@Endpoint(id = "codigo-vivo")
public class CodigoVivoEndpoint {
    @ReadOperation
    public Map<String, Object> status() {
        // Return operational status
    }
}
```

## 📊 Áreas para Contribuição

### Muito Bem-vindo 🎉

- [ ] Correção de bugs
- [ ] Testes (unit, integration, load)
- [ ] Documentação
- [ ] Otimizações de performance
- [ ] Novos exportadores (Loki, Jaeger)
- [ ] Integração com ferramentas (Vault, Consul)
- [ ] Exemplos de uso

### Precisa de Discussão 💬

- [ ] Mudanças na arquitetura
- [ ] Novos componentes
- [ ] Mudanças de API
- [ ] Suporte a novas linguagens

## 🔍 Padrões de Commit

Use conventional commits:

```
feat: add ability to disable hotspot detection
fix: correct off-by-one error in patch scoring
docs: update architecture documentation
style: reformat code with black
refactor: extract hotspot detection logic
perf: optimize prometheus query performance
test: add integration tests for detector
chore: update dependencies
```

## 📝 Padrão de Pull Request

```markdown
## Descrição
Descrição clara do que foi mudado.

## Tipo de Mudança
- [ ] Bug fix
- [ ] Nova feature
- [ ] Breaking change
- [ ] Documentação

## Como foi testado
Descreva os testes executados.

## Checklist
- [ ] Código segue o style guide
- [ ] Testes adicionados e passando
- [ ] Documentação atualizada
- [ ] Nenhuma warning de linting
- [ ] Sem quebra de features existentes
```

## 🚀 Release Process

1. Mantenedor atualiza versão em `setup.py`
2. Cria tag `v1.2.3`
3. CI/CD publica para registries
4. Documenta em CHANGELOG.md

## 📚 Documentação

Ao adicionar features:
1. Atualize README relevante
2. Adicione exemplo de uso
3. Documente endpoints da API
4. Atualize diagramas se aplicável

## 🐛 Relatório de Bugs

Inclua:
- Versão do projeto
- Passos para reproduzir
- Comportamento esperado
- Comportamento atual
- Logs relevantes
- Environment (OS, Python version, etc)

## ✨ Sugestões de Features

Descreva:
- Use case
- Benefício
- Possível implementação
- Trade-offs

## 📞 Contato

- Issues: GitHub Issues
- Discussões: GitHub Discussions
- Email: maintainers@codigovivo.ai

---

Obrigado por contribuir! 🙏
