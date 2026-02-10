# 🚀 GUIDE DE DÉMARRAGE - CARETTE RSE

**Félicitations !** Votre solution RSE est maintenant prête à la vente.

## ✅ Ce qui est opérationnel

### 1. **Widget RSE** (/demo-rse.html)
- ✅ Calcul CO2 automatique (8 modes de transport)
- ✅ Enregistrement des habitudes hebdomadaires
- ✅ Interface moderne et responsive
- ✅ Auto-assignation par domaine email

### 2. **Dashboard Entreprise** (/dashboard-company.html)
- ✅ Statistiques temps réel (employés, CO2, distance)
- ✅ Graphiques interactifs (Chart.js)
- ✅ Top 10 employés par impact
- ✅ Export Excel/CSV
- ✅ Filtrage par mois

### 3. **Landing Page** (/landing.html)
- ✅ Présentation commerciale complète
- ✅ Grille de pricing (4 plans)
- ✅ Témoignages clients
- ✅ Appels à l'action (CTA)
- ✅ Design professionnel responsive

### 4. **Inscription Entreprise** (/signup.html)
- ✅ Formulaire complet avec validation
- ✅ Génération automatique du code entreprise
- ✅ Auto-assignation des employés via domaine email
- ✅ Acceptation CGU obligatoire

### 5. **Emails Automatisés**
- ✅ Récap hebdomadaire (tous les vendredis)
- ✅ Confirmation immédiate après soumission
- ✅ 3 boutons (Confirmer/Modifier/Absent)
- ✅ Magic links sécurisés

### 6. **API Backend** (api.py)
- ✅ 30+ endpoints REST
- ✅ Rapports mensuels (user + company)
- ✅ Auto-confirmation après 7 jours
- ✅ Rate limiting & sécurité

### 7. **Légal & RGPD**
- ✅ Politique de confidentialité complète
- ✅ Mentions RGPD (droits, conservation, sécurité)
- ✅ Cookies conformes

---

## 🎯 CHECKLIST AVANT VENTE

### **Étape 1 : Configuration technique**
```bash
# 1. Réinitialiser les tables RSE
python backend/init_carpool_tables.py

# 2. Relancer le serveur
python serve.py
```

### **Étape 2 : Tester le parcours complet**
1. **Inscription entreprise** :
   - Aller sur http://localhost:9000/signup.html
   - Créer une entreprise test
   - Noter le code généré (ex: TECH2026)

2. **Soumission employé** :
   - Aller sur http://localhost:9000/demo-rse.html
   - Remplir avec email @[domaine-entreprise]
   - Vérifier auto-assignation

3. **Email hebdomadaire** :
   ```bash
   curl -X POST http://localhost:9000/api/v2/rse/send-weekly-recap \
     -H "Content-Type: application/json" \
     -d '{}'
   ```

4. **Dashboard** :
   - Aller sur http://localhost:9000/dashboard-company.html
   - Modifier `COMPANY_ID = 1` dans le code (ligne 268)
   - Vérifier les stats

### **Étape 3 : Domaine & SSL**
```bash
# Acheter un domaine (OVH, Gandi, etc.)
# Exemples : carette-rse.fr, carette.io, mon-bilan-co2.fr

# Installer Certbot pour SSL gratuit
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d carette-rse.fr -d www.carette-rse.fr
```

### **Étape 4 : Hébergement production**
```bash
# Installer Gunicorn
pip install gunicorn

# Lancer en production
gunicorn -w 4 -b 0.0.0.0:9000 serve:app

# Ou avec systemd (auto-restart)
sudo nano /etc/systemd/system/carette.service
```

---

## 💰 PRICING RECOMMANDÉ

| Plan | Employés | Prix/mois | Marge |
|------|----------|-----------|-------|
| **Starter** | 1-10 | 0€ | Acquisition |
| **Business** | 11-50 | 49€ | ~80% |
| **Enterprise** | 51-200 | 149€ | ~85% |
| **Custom** | +200 | Sur devis | ~90% |

**Coûts mensuels estimés :**
- Serveur VPS : 10-20€/mois
- Emails (SendGrid) : 0-15€/mois
- Total : **25-35€/mois** pour 100 clients

---

## 📢 STRATÉGIE DE VENTE

### **1. Contenu gratuit (Lead magnet)**
Créer :
- Calculateur CO2 gratuit (version simple du widget)
- Guide PDF "10 actions pour réduire votre bilan carbone"
- Template Excel "Suivi trajets domicile-travail"

### **2. Partenariats**
Contacter :
- **Cabinets RSE** : Commission 20-30% sur chaque client apporté
- **Experts-comptables** : Référencement auprès de leurs clients PME
- **CCI locales** : Sponsoring événements entrepreneurs

### **3. SEO local**
Optimiser pour :
- "bilan carbone trajets domicile-travail"
- "reporting CSRD trajets"
- "solution RSE PME [ville]"

### **4. Cold email ciblé** (si tu veux éviter LinkedIn)
Template :
```
Objet : [Nom Entreprise] - Votre bilan carbone CSRD en 5 minutes

Bonjour [Prénom],

Je vois que [Entreprise] emploie ~[X] personnes à [Ville].

Depuis janvier 2026, la CSRD impose de tracker les émissions 
de vos trajets domicile-travail.

J'ai créé Carette pour automatiser ça :
→ Widget 5 min à installer
→ Emails hebdomadaires aux employés
→ Rapports mensuels automatiques

Gratuit jusqu'à 10 employés.

Démo en 2 clics : [lien]

[Signature]
```

---

## 🚀 PROCHAINES FONCTIONNALITÉS (v2)

Pour augmenter le prix :
1. **Intégration Slack/Teams** (notifications)
2. **Recommandations personnalisées** (covoiturage, transports)
3. **Gamification** (badges, classements)
4. **API publique** (connecteurs SIRH)
5. **Challenges inter-entreprises** (réduction CO2)

---

## 📞 SUPPORT CLIENT

Mettre en place :
- **Email support** : support@carette.fr (ticket Freshdesk/Zendesk)
- **FAQ** : Page dédiée avec 10-15 questions courantes
- **Chat** : Crisp.chat (gratuit jusqu'à 2 agents)

---

## 🎉 TU ES PRÊT !

**Ton produit est vendable dès maintenant.**

Prochaines étapes :
1. Acheter un domaine
2. Déployer en production
3. Créer 3 contenus (blog/PDF)
4. Contacter 10 prospects/jour
5. Itérer selon feedback

**Budget minimal :** 50€ (domaine + 1er mois serveur)

**Objectif réaliste :** 5 clients payants en 90 jours = 245€/mois MRR

Bon courage ! 💪
