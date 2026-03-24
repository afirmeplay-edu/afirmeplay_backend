# 🎨 Frontend: Guia para Chamadas de API com Admin

## 📋 Resumo Rápido

**Usuários Comuns** (Aluno, Professor, Coordenador, Diretor, TecAdm):

- ✅ Apenas enviam `Authorization: Bearer <token>`
- ✅ Tudo funciona automaticamente

**Usuário Admin**:

- ⚠️ Precisa fornecer **contexto de cidade** para rotas tenant
- ✅ Enviar headers extras: `X-City-ID` ou `X-City-Slug`

---

## 🔐 Fluxo de Autenticação

### 1. Login

Mesma chamada para todos os usuários:

```javascript
const login = async (email, password) => {
	const response = await fetch("http://localhost:5000/login", {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
		},
		body: JSON.stringify({ email, password }),
	});

	const data = await response.json();

	// Armazenar token e informações do usuário
	localStorage.setItem("token", data.token);
	localStorage.setItem("user", JSON.stringify(data.user));

	return data;
};
```

**Response do Login:**

```javascript
// Usuário Comum (Professor, TecAdm, etc)
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid-123",
    "name": "Prof. João Silva",
    "email": "prof@escola.com",
    "role": "professor",
    "tenant_id": "city-abc-123",      // ← TEM city_id
    "city_slug": "jiparana"            // ← TEM slug
  }
}

// Admin
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid-admin",
    "name": "Administrador",
    "email": "admin@sistema.com",
    "role": "admin",
    "tenant_id": null,                 // ← NÃO tem city_id
    "city_slug": null                  // ← NÃO tem slug
  }
}
```

---

## 📞 Chamadas de API

### Para Usuários Comuns

**Simples:** Apenas adicionar Authorization header

```javascript
const listarEscolas = async () => {
	const token = localStorage.getItem("token");

	const response = await fetch("http://localhost:5000/school", {
		method: "GET",
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});

	return await response.json();
};

// ✅ Funciona! Retorna escolas do município do usuário
```

---

### Para Admin

#### Opção 1: Rotas Globais (Sem Contexto)

Admin pode acessar rotas globais **sem** especificar cidade:

```javascript
// ✅ FUNCIONA: Listar todas as cidades
const listarCidades = async () => {
	const token = localStorage.getItem("token");

	const response = await fetch("http://localhost:5000/city", {
		method: "GET",
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});

	return await response.json();
};
```

**Rotas Globais (não precisam de contexto):**

- `GET /city` - Listar cidades
- `POST /city` - Criar cidade
- `GET /login`
- `GET /logout`

#### Opção 2: Rotas Tenant COM Header X-City-Slug

Para acessar dados de um município específico, adicionar header:

```javascript
// ✅ FUNCIONA: Listar escolas de Jiparaná
const listarEscolas = async (citySlug) => {
	const token = localStorage.getItem("token");

	const response = await fetch("http://localhost:5000/school", {
		method: "GET",
		headers: {
			Authorization: `Bearer ${token}`,
			"X-City-Slug": citySlug, // ← ADICIONAR ESTE HEADER
		},
	});

	return await response.json();
};

// Uso:
listarEscolas("jiparana"); // Escolas de Jiparaná
listarEscolas("portovelho"); // Escolas de Porto Velho
```

#### Opção 3: Rotas Tenant COM Header X-City-ID

Alternativa usando UUID da cidade:

```javascript
// ✅ FUNCIONA: Listar escolas usando UUID
const listarEscolas = async (cityId) => {
	const token = localStorage.getItem("token");

	const response = await fetch("http://localhost:5000/school", {
		method: "GET",
		headers: {
			Authorization: `Bearer ${token}`,
			"X-City-ID": cityId, // ← UUID da cidade
		},
	});

	return await response.json();
};

// Uso:
listarEscolas("abc-123-def-456");
```

#### ❌ Opção ERRADA: Admin Sem Contexto em Rota Tenant

```javascript
// ❌ NÃO FUNCIONA: Admin sem header em rota tenant
const listarEscolas = async () => {
  const token = localStorage.getItem('token');

  const response = await fetch('http://localhost:5000/school', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
      // Faltou X-City-Slug ou X-City-ID!
    }
  });

  return await response.json();
};

// Response 403:
{
  "erro": "Contexto de cidade obrigatório para esta operação",
  "mensagem": "Esta rota exige que você especifique um município...",
  "opcoes": [
    "X-City-ID: <uuid-da-cidade>",
    "X-City-Slug: <slug-da-cidade>"
  ]
}
```

---

## 🎯 Helper Functions Recomendadas

### 1. Função Genérica de API

```javascript
const apiCall = async (url, options = {}) => {
	const token = localStorage.getItem("token");
	const user = JSON.parse(localStorage.getItem("user") || "{}");

	// Headers base
	const headers = {
		Authorization: `Bearer ${token}`,
		"Content-Type": "application/json",
		...options.headers,
	};

	// Se admin E forneceu citySlug, adicionar header
	if (user.role === "admin" && options.citySlug) {
		headers["X-City-Slug"] = options.citySlug;
	}

	// Se admin E forneceu cityId, adicionar header
	if (user.role === "admin" && options.cityId) {
		headers["X-City-ID"] = options.cityId;
	}

	const response = await fetch(url, {
		...options,
		headers,
	});

	if (!response.ok) {
		const error = await response.json();
		throw new Error(error.erro || "Erro na requisição");
	}

	return await response.json();
};

// Uso:
// Usuário comum (automático)
const escolas = await apiCall("http://localhost:5000/school");

// Admin com contexto
const escolas = await apiCall("http://localhost:5000/school", {
	citySlug: "jiparana",
});
```

### 2. Hook React (Admin Context)

```javascript
import { useState, useEffect } from "react";

const useAdminContext = () => {
	const [selectedCity, setSelectedCity] = useState(null);
	const [cities, setCities] = useState([]);
	const user = JSON.parse(localStorage.getItem("user") || "{}");
	const isAdmin = user.role === "admin";

	// Carregar cidades (apenas admin)
	useEffect(() => {
		if (isAdmin) {
			apiCall("http://localhost:5000/city")
				.then(setCities)
				.catch(console.error);
		}
	}, [isAdmin]);

	// Helper para adicionar contexto nas chamadas
	const withContext = (options = {}) => {
		if (!isAdmin) return options;

		return {
			...options,
			citySlug: selectedCity?.slug,
			cityId: selectedCity?.id,
		};
	};

	return {
		isAdmin,
		selectedCity,
		setSelectedCity,
		cities,
		withContext,
	};
};

// Uso no componente:
function EscolasPage() {
	const { isAdmin, selectedCity, setSelectedCity, cities, withContext } =
		useAdminContext();
	const [escolas, setEscolas] = useState([]);

	// Admin precisa selecionar cidade
	useEffect(() => {
		if (isAdmin && !selectedCity) {
			return; // Aguardar seleção
		}

		// Carregar escolas
		apiCall("http://localhost:5000/school", withContext())
			.then(setEscolas)
			.catch(console.error);
	}, [selectedCity]);

	return (
		<div>
			{isAdmin && (
				<select
					onChange={(e) => setSelectedCity(cities[e.target.value])}>
					<option value="">Selecione um município</option>
					{cities.map((city, idx) => (
						<option key={city.id} value={idx}>
							{city.name} - {city.state}
						</option>
					))}
				</select>
			)}

			<ul>
				{escolas.map((escola) => (
					<li key={escola.id}>{escola.name}</li>
				))}
			</ul>
		</div>
	);
}
```

### 3. Service Class

```javascript
class ApiService {
	constructor() {
		this.baseURL = "http://localhost:5000";
		this.token = localStorage.getItem("token");
		this.user = JSON.parse(localStorage.getItem("user") || "{}");
	}

	isAdmin() {
		return this.user.role === "admin";
	}

	async request(endpoint, options = {}) {
		const headers = {
			Authorization: `Bearer ${this.token}`,
			"Content-Type": "application/json",
			...options.headers,
		};

		// Admin: adicionar contexto se fornecido
		if (this.isAdmin()) {
			if (options.citySlug) {
				headers["X-City-Slug"] = options.citySlug;
			}
			if (options.cityId) {
				headers["X-City-ID"] = options.cityId;
			}
		}

		const response = await fetch(`${this.baseURL}${endpoint}`, {
			...options,
			headers,
		});

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.erro || "Erro na requisição");
		}

		return await response.json();
	}

	// Rotas Globais (sem contexto)
	async getCities() {
		return this.request("/city");
	}

	// Rotas Tenant (com contexto)
	async getSchools(citySlug) {
		const options = this.isAdmin() && citySlug ? { citySlug } : {};
		return this.request("/school", options);
	}

	async getStudents(citySlug) {
		const options = this.isAdmin() && citySlug ? { citySlug } : {};
		return this.request("/students", options);
	}

	async getClasses(citySlug) {
		const options = this.isAdmin() && citySlug ? { citySlug } : {};
		return this.request("/classes", options);
	}
}

// Uso:
const api = new ApiService();

// Usuário comum (automático)
const escolas = await api.getSchools();

// Admin (fornece cidade)
const escolas = await api.getSchools("jiparana");
```

---

## 🎨 UI/UX Recomendações

### Para Admin: Seletor de Município

```jsx
function CitySelector({ onCitySelect }) {
	const [cities, setCities] = useState([]);
	const user = JSON.parse(localStorage.getItem("user") || "{}");

	useEffect(() => {
		if (user.role === "admin") {
			apiCall("http://localhost:5000/city").then(setCities);
		}
	}, []);

	if (user.role !== "admin") {
		return null; // Não mostrar para usuários comuns
	}

	return (
		<div className="city-selector">
			<label>Município:</label>
			<select onChange={(e) => onCitySelect(cities[e.target.value])}>
				<option value="">Selecione...</option>
				{cities.map((city, idx) => (
					<option key={city.id} value={idx}>
						{city.name} - {city.state}
					</option>
				))}
			</select>
		</div>
	);
}
```

### Feedback de Contexto

```jsx
function ContextBadge() {
	const user = JSON.parse(localStorage.getItem("user") || "{}");

	if (user.role !== "admin") {
		return (
			<div className="badge">📍 {user.city_slug || "Carregando..."}</div>
		);
	}

	const selectedCity = sessionStorage.getItem("selectedCitySlug");

	return (
		<div className="badge admin-badge">
			👑 Admin {selectedCity && `→ ${selectedCity}`}
		</div>
	);
}
```

---

## 📋 Checklist de Implementação

### 1. Detectar Tipo de Usuário

```javascript
const user = JSON.parse(localStorage.getItem("user") || "{}");
const isAdmin = user.role === "admin";
const hasCity = user.tenant_id !== null;
```

### 2. Interface Admin

- [ ] Adicionar seletor de município
- [ ] Mostrar cidade selecionada no header
- [ ] Permitir trocar de cidade sem recarregar
- [ ] Salvar última cidade selecionada (sessionStorage)

### 3. Chamadas de API

- [ ] Criar função helper que adiciona headers automaticamente
- [ ] Adicionar X-City-Slug para rotas tenant quando admin
- [ ] Tratar erro 403 (contexto obrigatório)
- [ ] Tratar erro 404 (município não encontrado)

### 4. Validações

- [ ] Bloquear acesso a rotas tenant se admin não selecionou cidade
- [ ] Mostrar mensagem: "Selecione um município para continuar"
- [ ] Liberar rotas globais para admin sem seleção

---

## ⚠️ Erros Comuns e Soluções

### Erro 1: Admin Não Consegue Ver Escolas

**Problema:**

```javascript
// Admin tentando acessar sem contexto
fetch("/school", {
	headers: { Authorization: "Bearer token" },
});

// Response 403
```

**Solução:**

```javascript
// Adicionar X-City-Slug
fetch("/school", {
	headers: {
		Authorization: "Bearer token",
		"X-City-Slug": "jiparana", // ← ADICIONAR
	},
});
```

### Erro 2: Headers Não Funcionam

**Problema:** Headers X-City-\* não estão sendo enviados

**Causa:** CORS bloqueando headers customizados

**Solução:** Backend já está configurado. Verificar se:

```javascript
// Headers corretos (case-sensitive!)
"X-City-Slug"; // ✅ Correto
"x-city-slug"; // ❌ Pode não funcionar
"X-CITY-SLUG"; // ❌ Pode não funcionar
```

### Erro 3: Usuário Comum Não Vê Dados

**Problema:** Usuário comum sem dados

**Causa Possível:** `tenant_id` não está no token

**Solução:** Verificar response do login:

```javascript
console.log(data.user.tenant_id); // Deve existir!
```

---

## 🚀 Exemplo Completo (React)

```jsx
import { useState, useEffect } from "react";

function App() {
	const [user, setUser] = useState(null);
	const [selectedCity, setSelectedCity] = useState(null);
	const [cities, setCities] = useState([]);
	const [escolas, setEscolas] = useState([]);

	// Login
	const handleLogin = async (email, password) => {
		const response = await fetch("http://localhost:5000/login", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ email, password }),
		});

		const data = await response.json();
		localStorage.setItem("token", data.token);
		setUser(data.user);
	};

	// Carregar cidades (apenas admin)
	useEffect(() => {
		if (user?.role === "admin") {
			fetch("http://localhost:5000/city", {
				headers: {
					Authorization: `Bearer ${localStorage.getItem("token")}`,
				},
			})
				.then((r) => r.json())
				.then(setCities);
		}
	}, [user]);

	// Carregar escolas
	useEffect(() => {
		if (!user) return;

		// Admin precisa selecionar cidade
		if (user.role === "admin" && !selectedCity) {
			return;
		}

		const headers = {
			Authorization: `Bearer ${localStorage.getItem("token")}`,
		};

		// Admin: adicionar contexto
		if (user.role === "admin" && selectedCity) {
			headers["X-City-Slug"] = selectedCity.slug;
		}

		fetch("http://localhost:5000/school", { headers })
			.then((r) => r.json())
			.then(setEscolas)
			.catch((err) => {
				if (err.message.includes("403")) {
					alert("Selecione um município primeiro!");
				}
			});
	}, [user, selectedCity]);

	if (!user) {
		return <LoginForm onLogin={handleLogin} />;
	}

	return (
		<div>
			<h1>Olá, {user.name}!</h1>

			{/* Seletor de cidade (apenas admin) */}
			{user.role === "admin" && (
				<div>
					<label>Município:</label>
					<select
						onChange={(e) =>
							setSelectedCity(cities[e.target.value])
						}>
						<option value="">Selecione...</option>
						{cities.map((city, idx) => (
							<option key={city.id} value={idx}>
								{city.name}
							</option>
						))}
					</select>
				</div>
			)}

			{/* Badge de contexto */}
			<div>
				{user.role === "admin"
					? `Admin → ${selectedCity?.name || "Nenhum município selecionado"}`
					: `Município: ${user.city_slug}`}
			</div>

			{/* Lista de escolas */}
			<h2>Escolas</h2>
			<ul>
				{escolas.map((escola) => (
					<li key={escola.id}>{escola.name}</li>
				))}
			</ul>
		</div>
	);
}
```

---

## 📚 Resumo para Frontend

| Tipo de Usuário         | Headers Necessários                            | Observações     |
| ----------------------- | ---------------------------------------------- | --------------- |
| **Comum**               | `Authorization` apenas                         | Tudo automático |
| **Admin → Rota Global** | `Authorization` apenas                         | Sem contexto OK |
| **Admin → Rota Tenant** | `Authorization` + `X-City-Slug` ou `X-City-ID` | Obrigatório!    |

**Headers:**

- `Authorization: Bearer <token>` - Sempre obrigatório
- `X-City-Slug: <slug>` - Admin em rotas tenant (recomendado)
- `X-City-ID: <uuid>` - Admin em rotas tenant (alternativa)

**Rotas Tenant** (exigem contexto para admin):

- `/school`, `/students`, `/class`, `/test`, `/evaluations`, `/reports`, `/dashboard`, `/physical-test`, `/answer-sheets`, `/certificates`

**Rotas Globais** (não exigem contexto):

- `/city`, `/login`, `/logout`

---

**Criado em:** 2026-02-10  
**Para dúvidas:** Ver COMO_FUNCIONA_MULTITENANT.md
