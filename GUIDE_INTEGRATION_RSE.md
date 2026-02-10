# 🌱 Guide d'Intégration Widget RSE

## 📝 Processus d'Inscription

### Étape 1 : Inscription de l'entreprise

Rendez-vous sur la page d'inscription :
```
http://51.178.30.246:9000/signup.html
```

**Informations requises :**
- Nom de l'entreprise
- SIREN (optionnel)
- Domaine email (ex: `decathlon.fr`)
- Contact (nom + email professionnel)
- Adresse du siège
- Sites de l'entreprise (optionnel)

**Résultat :**
- Un **code entreprise unique** est généré (ex: `DECA2026`)
- Une **clé d'accès** sécurisée est créée
- Un **lien vers le dashboard** est fourni

---

### Étape 2 : Intégration du Widget

Une fois le code obtenu, intégrez le widget en **1 ligne de code** :

```html
<carpool-offer-widget 
    data-mode="rse"
    data-company-code="DECA2026"
>
</carpool-offer-widget>

<!-- Chargement du script -->
<script type="module" src="https://votre-domaine.com/frontend/carpool-widget.js"></script>
```

#### Attributs obligatoires

| Attribut | Description | Exemple |
|----------|-------------|---------|
| `data-mode` | Mode du widget | `"rse"` |
| `data-company-code` | Code unique de l'entreprise | `"DECA2026"` |

#### Attributs optionnels (personnalisation)

| Attribut | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `color-outbound` | Couleur aller | `#10b981` (vert) |
| `color-return` | Couleur retour | `#f59e0b` (orange) |
| `detour-color` | Couleur détour | `#34d399` |
| `theme` | Thème visuel | `"light"` ou `"dark"` |
| `font-family` | Police personnalisée | Système par défaut |

---

## 🔐 Validation Automatique

Le widget **valide automatiquement** le code entreprise au chargement :

1. **Code valide** → Le widget se charge normalement
2. **Code invalide** → Message d'erreur avec lien vers la page d'inscription
3. **Code manquant** → Message d'erreur invitant à fournir le code

### Fonctionnement

```javascript
// Au chargement du widget (connectedCallback)
GET /api/v2/companies/verify-code?code=DECA2026

// Réponse succès (200)
{
  "valid": true,
  "company_id": 1,
  "company_name": "Decathlon",
  "company_code": "DECA2026",
  "email_domain": "decathlon.fr",
  "sites": [...]
}

// Réponse erreur (404)
{
  "error": "Code entreprise 'DECA2026' non trouvé",
  "valid": false
}
```

---

## 📊 Dashboard Entreprise

Accédez au tableau de bord pour suivre les statistiques RSE :

```
http://51.178.30.246:9000/dashboard-company.html?token=VOTRE_MAGIC_TOKEN
```

**Fonctionnalités :**
- Suivi des émissions CO₂
- Répartition des modes de transport
- Évolution mois/année
- Top 10 des employés
- Carte thermique des domiciles

---

## 🔄 Workflow Complet

```
1. Entreprise s'inscrit sur signup.html
   ↓
2. Reçoit code DECA2026
   ↓
3. Intègre widget avec data-company-code="DECA2026"
   ↓
4. Widget valide le code via API
   ↓
5. Employés utilisent le widget (saisie trajets)
   ↓
6. Email de confirmation envoyé
   ↓
7. Chaque vendredi à 16h : email récapitulatif
   ↓
8. Dashboard entreprise pour suivi global
```

---

## ❌ Gestion des Erreurs

### Code manquant
```html
<!-- ❌ Incorrect -->
<carpool-offer-widget data-mode="rse"></carpool-offer-widget>
```
**Erreur affichée :** "Code entreprise manquant"

### Code invalide
```html
<!-- ❌ Code n'existe pas en base -->
<carpool-offer-widget 
    data-mode="rse"
    data-company-code="FAKE123"
>
</carpool-offer-widget>
```
**Erreur affichée :** "Le code 'FAKE123' n'existe pas ou n'est pas actif"

### Solution
→ Le message d'erreur contient un lien direct vers `/signup.html`

---

## 🎯 Exemple Complet

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>RSE - Decathlon</title>
</head>
<body>
    <h1>🌱 Mobilité Durable - Decathlon</h1>
    
    <carpool-offer-widget 
        data-mode="rse"
        data-company-code="DECA2026"
        color-outbound="#10b981"
        theme="light"
    >
    </carpool-offer-widget>
    
    <script type="module" src="/frontend/carpool-widget.js"></script>
</body>
</html>
```

---

## 📞 Support

Pour toute question :
- Email : support@carette.app
- Documentation : `/docs/WEEKLY_RSE_RECAP.md`
- Démo : `http://51.178.30.246:9000/demo-rse.html`
