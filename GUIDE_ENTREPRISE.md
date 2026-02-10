# 🚀 Guide Entreprise - Carette RSE

## 📋 Qu'est-ce que Carette ?

Carette est une solution de **reporting carbone mobilité** conforme à la directive CSRD. Elle permet à votre entreprise de :

- ✅ Collecter automatiquement les données de mobilité domicile-travail
- ✅ Calculer les émissions CO2 de vos employés
- ✅ Générer des rapports pour votre bilan carbone
- ✅ Faciliter le covoiturage entre employés (optionnel)

**Prix : 49€/mois** - Sans engagement

---

## 🎯 Démarrage rapide (5 minutes)

### Étape 1 : Inscription entreprise

1. Allez sur `https://votredomaine.com/signup.html`
2. Remplissez les informations :
   - Nom de l'entreprise
   - SIREN (optionnel)
   - Domaine email (ex: `votreentreprise.fr`)
   - Email de contact
   - Sites de l'entreprise (avec adresses)

3. **IMPORTANT** : Notez votre **code entreprise** (ex: `TECH2026`) et sauvegardez le lien du dashboard

### Étape 2 : Déployer le widget sur votre intranet

Ajoutez ce code HTML sur votre intranet (page d'accueil, portail RH, etc.) :

```html
<!-- Widget Carette RSE -->
<carpool-offer-widget 
    data-mode="rse"
    data-company-code="VOTRE_CODE_ICI"
    api-url="https://votredomaine.com"
>
</carpool-offer-widget>

<script type="module" src="https://votredomaine.com/frontend/carpool-widget.js"></script>
```

**Remplacez `VOTRE_CODE_ICI`** par le code fourni à l'inscription (ex: `TECH2026`)

### Étape 3 : Communiquer aux employés

Envoyez un email à vos employés :

---

**Objet** : 🌱 Nouvelle plateforme mobilité - Déclaration trajets domicile-travail

Bonjour,

Dans le cadre de notre démarche RSE et conformité CSRD, nous avons mis en place un outil de déclaration de vos trajets domicile-travail.

**Comment ça marche ?**
1. Allez sur notre intranet : [LIEN]
2. Remplissez votre adresse domicile et adresse de travail
3. Sélectionnez vos modes de transport pour chaque jour de la semaine
4. Validez

**Temps nécessaire** : 2 minutes
**Fréquence** : 1 fois par mois (ou en cas de changement)

Merci de votre participation ! 🚴🚗🚌

---

### Étape 4 : Consulter le dashboard

Accédez à votre dashboard via le lien fourni lors de l'inscription :
`https://votredomaine.com/dashboard-company.html?company_id=X&access_key=XXX`

**Fonctionnalités** :
- 📊 Visualisation des émissions CO2 par période
- 🗺️ Carte de chaleur des domiciles de vos employés
- 📈 Répartition par mode de transport
- 📅 Évolution hebdomadaire

---

## 🔐 Sécurité & RGPD

### Données collectées
- Nom, email, téléphone (optionnel)
- Adresse domicile → **géocodée** (seules les coordonnées GPS sont stockées, pas l'adresse exacte)
- Adresse de travail
- Modes de transport par jour
- Distance domicile-travail

### Conformité
- ✅ **RGPD** : Données hébergées en France, droit d'accès/suppression
- ✅ **Anonymisation** : Les adresses sont converties en coordonnées GPS
- ✅ **Opt-out** : Lien de désinscription dans chaque email
- ✅ **Sécurité** : Accès entreprise via clé API, pas de partage cross-entreprise

### Suppression de données
Un employé peut :
- Se désinscrire via le lien dans l'email de récap
- Demander la suppression de son compte (contactez-nous)

---

## 📧 Emails automatiques

### Email hebdomadaire (vendredi)
Chaque vendredi, vos employés reçoivent un email avec :
- Récapitulatif de leur semaine (transports utilisés, CO2 émis)
- Lien de confirmation (1 clic)
- Possibilité de modifier leurs déclarations

### Email de déménagement
Si un employé déménage, il peut cliquer sur "🏠 J'ai déménagé" dans l'email pour :
- Mettre à jour son adresse
- Revoir ses modes de transport

---

## ⚙️ Gestion des employés

Accédez à la page de gestion : `Bouton "⚙️ Gestion"` dans le dashboard

**Actions possibles** :
- ✅ Voir la liste des employés inscrits
- ✅ Désactiver un employé (départ de l'entreprise)
- ✅ Réactiver un employé
- ✅ Gérer les sites (ajouter/désactiver)

**Note** : Les données historiques sont **toujours conservées** même si un employé est désactivé (pour le bilan carbone annuel).

---

## 🆘 Support

### FAQ

**Q : Un employé n'a pas reçu l'email de confirmation ?**
R : Vérifiez les spams. L'email vient de `noreply@votredomaine.com`

**Q : Comment modifier un site ?**
R : Dashboard → ⚙️ Gestion → Configuration → Modifier/Désactiver

**Q : Les employés doivent-ils créer un compte ?**
R : Non ! Ils remplissent simplement le formulaire via le widget. Un compte est créé automatiquement.

**Q : Combien de temps sont conservées les données ?**
R : 3 ans (conformité CSRD). Suppression possible sur demande.

**Q : Peut-on exporter les données ?**
R : Oui, contactez le support pour un export CSV.

### Contact
- 📧 Email : support@carette.app
- 💬 Chat : [À venir]
- 📞 Téléphone : [À venir pour abonnement Pro]

---

## 💰 Facturation

### Tarif actuel : 49€/mois HT
- ✅ Utilisateurs illimités
- ✅ Sites illimités
- ✅ Dashboard + rapports
- ✅ Support email
- ✅ Mises à jour incluses

### Méthode de paiement
- Carte bancaire (mensuel)
- Virement (annuel, -10%)

### Résiliation
Sans engagement. Résiliable à tout moment depuis le dashboard.

---

## 🔄 Mises à jour

**Dernière version** : v2.0 (Janvier 2026)
- ✅ Multi-entreprises
- ✅ Géocodage automatique
- ✅ Dashboard carbone
- ✅ Emails de confirmation
- ✅ Système de déménagement

**Prochainement** :
- Export CSV/Excel
- Intégration Google Calendar (covoiturage)
- API externe pour ERP
- Application mobile

---

## 📚 Ressources

- [Documentation technique](./README.md)
- [Guide modification widget](./GUIDE_MODIFICATION_WIDGET.md)
- [Sécurité](./SECURITY_GUIDE.md)
- [Changelog](./CHANGELOG.md)

---

**Besoin d'aide ?** Contactez-nous : support@carette.app
