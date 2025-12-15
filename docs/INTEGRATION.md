# Carette - Guide d'Intégration

## 🎯 Installation en 5 minutes

### Méthode 1 : Intégration directe (HTML + JS)

La façon la plus simple d'intégrer Carette sur votre site.

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Mon Événement - Covoiturage</title>
</head>
<body>
    <!-- Votre contenu -->
    
    <!-- Widget Carette -->
    <carpool-offer-widget 
        color-outbound="#c47cff" 
        color-return="#ff9c3f"
        theme="light"
        event-id="mon-concert-2025"
        event-name="Festival Rock 2025"
        event-location="Zénith de Paris"
        event-date="2025-08-20"
        event-time="20:00"
    ></carpool-offer-widget>

    <!-- Script (charger une seule fois) -->
    <script type="module" src="https://cdn.carette.app/v1/widget.js"></script>
</body>
</html>
```

**C'est tout !** Le widget est opérationnel.

---

### Méthode 2 : Self-hosted

Si vous préférez héberger le code vous-même :

```bash
# 1. Télécharger le widget
curl -O https://cdn.carette.app/v1/widget.js

# 2. L'inclure depuis votre serveur
<script type="module" src="/static/widget.js"></script>
```

---

## 🎨 Personnalisation

### Couleurs et thème

```html
<carpool-offer-widget 
    color-outbound="#7c3aed"     <!-- Violet pour l'aller -->
    color-return="#f97316"        <!-- Orange pour le retour -->
    detour-color="#fbbf24"        <!-- Jaune pour les détours -->
    theme="dark"                  <!-- Mode sombre -->
    font-family="'Inter', sans-serif"
></carpool-offer-widget>
```

### Pré-remplissage automatique

Le widget détecte automatiquement les métadonnées de l'événement :

```html
<carpool-offer-widget 
    event-id="unique-event-123"
    event-name="Match RC Lens vs PSG"
    event-location="Stade Bollaert-Delelis, Lens"
    event-date="2025-12-20"
    event-time="21:00"
    page-url="https://votresite.com/match/123"
></carpool-offer-widget>
```

Les utilisateurs n'auront plus qu'à saisir leur point de départ !

---

## 🔗 Intégrations populaires

### WordPress

```php
// Dans votre template ou shortcode
echo '<carpool-offer-widget 
    event-id="' . get_the_ID() . '"
    event-name="' . get_the_title() . '"
    event-date="' . get_field('event_date') . '"
></carpool-offer-widget>';
```

```html
<!-- Dans le footer -->
<script type="module" src="https://cdn.carette.app/v1/widget.js"></script>
```

---

### React

```jsx
import { useEffect } from 'react';

function EventPage({ event }) {
  useEffect(() => {
    // Charger le script du widget
    const script = document.createElement('script');
    script.src = 'https://cdn.carette.app/v1/widget.js';
    script.type = 'module';
    document.body.appendChild(script);
    
    return () => document.body.removeChild(script);
  }, []);

  return (
    <div>
      <h1>{event.name}</h1>
      
      <carpool-offer-widget 
        event-id={event.id}
        event-name={event.name}
        event-location={event.venue}
        event-date={event.date}
        event-time={event.time}
      />
    </div>
  );
}
```

---

### Vue.js

```vue
<template>
  <div>
    <h1>{{ event.name }}</h1>
    
    <carpool-offer-widget 
      :event-id="event.id"
      :event-name="event.name"
      :event-location="event.venue"
      :event-date="event.date"
      :event-time="event.time"
    />
  </div>
</template>

<script setup>
import { onMounted } from 'vue';

onMounted(() => {
  const script = document.createElement('script');
  script.src = 'https://cdn.carette.app/v1/widget.js';
  script.type = 'module';
  document.body.appendChild(script);
});
</script>
```

---

### Wix / Squarespace / Webflow

1. Ajoutez un **bloc HTML personnalisé**
2. Collez ce code :

```html
<carpool-offer-widget 
    event-id="mon-evenement"
    event-name="Mon Super Concert"
    event-date="2025-09-01"
    event-time="19:00"
></carpool-offer-widget>

<script type="module" src="https://cdn.carette.app/v1/widget.js"></script>
```

3. Sauvegardez et publiez !

---

## 📱 Responsive

Le widget s'adapte automatiquement à toutes les tailles d'écran :
- **Desktop** : Carte interactive plein écran
- **Tablet** : Layout optimisé
- **Mobile** : Interface tactile, carte réduite

Pas de CSS supplémentaire nécessaire.

---

## 🔌 API Backend (optionnel)

Si vous voulez votre propre backend :

```bash
# 1. Cloner le repo
git clone https://github.com/carette/carette.git
cd carette/backend

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer la DB
python sql.py

# 4. Lancer l'API
python api.py
# → API sur http://localhost:5001
```

Puis pointer le widget vers votre API :

```html
<carpool-offer-widget 
    api-url="https://votre-serveur.com/api"
    ...
></carpool-offer-widget>
```

---

## 🎫 Cas d'usage : Billetterie

Intégration post-achat pour proposer le covoiturage après achat du ticket :

```html
<!-- Page de confirmation de commande -->
<div class="order-success">
  <h2>✅ Votre billet est confirmé !</h2>
  <p>Profitez-en pour organiser votre trajet :</p>
  
  <carpool-offer-widget 
      event-id="<?= $order->event_id ?>"
      event-name="<?= $order->event_name ?>"
      event-date="<?= $order->event_date ?>"
      user-email="<?= $user->email ?>"
  ></carpool-offer-widget>
</div>
```

---

## 📊 Analytics (TODO)

Dashboard en préparation pour suivre :
- Nombre d'offres créées
- Taux de remplissage moyen
- CO₂ évité estimé
- Cartes de chaleur des trajets

---

## 🆘 Support

- **Documentation** : [docs.carette.app](https://docs.carette.app)
- **GitHub Issues** : [github.com/carette/issues](https://github.com/carette/issues)
- **Email** : support@carette.app

---

**Prêt à lancer ?** Testez la [démo interactive](https://carette.app/demo) !
