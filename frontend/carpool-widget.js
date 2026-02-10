class CarpoolOfferWidget extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    
    // Détection du mode widget (ponctuel, récurrent ou rse)
    this.widgetMode = this.getAttribute('data-mode') || 'ponctual';
    
    // Données entreprise B2B
    this.companyId = this.getAttribute('data-company-id') || null;
    this.companyName = this.getAttribute('data-company-name') || null;
    this.companyCode = this.getAttribute('data-company-code') || '';
    this.companySites = [];
    try {
      const sitesAttr = this.getAttribute('data-sites');
      if (sitesAttr) {
        this.companySites = JSON.parse(sitesAttr);
      }
    } catch (e) {
      console.error('❌ Erreur parsing data-sites:', e);
    }
    
    console.log('🔧 Widget Mode:', this.widgetMode, 'Company:', this.companyName, 'Company ID:', this.companyId, 'Sites:', this.companySites.length);
    
    // API de routing - OSRM avec fallback multi-serveurs
    // NOTE: N'utilisez JAMAIS de clés API côté client
    this.OSRM_SERVERS = [
      'https://router.project-osrm.org',
      'https://routing.openstreetmap.de/routed-car',
      'http://router.project-osrm.org',  // Version HTTP en fallback
      'https://osrm.parisdata.gouv.fr'   // Serveur public Paris
    ];
    this.OSRM_URL = this.OSRM_SERVERS[0]; // Pour compatibilité
    
    // SÉCURITÉ: Les clés API doivent être gérées côté backend via un proxy
    // Ne PAS mettre de clés API directement dans le frontend
    // Utilisez l'attribut 'api-url' pour pointer vers votre backend
    this.API_URL = this.getAttribute('api-url') || window.location.origin;
    
    // Couleurs thématiques pour l'aller et le retour (valeurs par défaut, seront écrasées dans connectedCallback)
    this.colorOutbound = '#7c3aed'; // Violet pour l'aller (défaut)
    this.colorReturn = '#f97316'; // Orange pour le retour (défaut)
    this.detourColor = '#fbbf24'; // Jaune pour les détours (défaut)
    
    // Police personnalisable via attribut
    this.fontFamily = this.getAttribute('font-family') || '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif';
    
    // Mode jour/nuit (personnalisable via attribut)
    this.theme = this.getAttribute('theme') || 'light'; // 'light' ou 'dark'
    
    // Couleurs de détour (seront initialisées dans connectedCallback)
    this.detourColorDark = '#d97706';
    this.detourShadow = 'rgba(251, 191, 36, 0.18)';
    
    this.startCoords = null;
    this.endCoords = null; // Initialize end coordinates
    this.map = null;
    this.routeLayerId = "route-line";
    this.startMarker = null;
    this.endMarker = null;
    // Onglet actif: 'find' (trouver un covoit) ou 'offer' (proposer un covoit)
    this.activeTab = 'find';
    this.setAttribute('data-active-tab', 'find');
    // Points d'étape (coords) et marqueurs
    this.stopCoords = [];
    this.stopMarkers = [];
  this.stopTimes = [];
  this.fromTime = null;
  this.toTime = null;
  // Custom editable times (timestamps) for timeline stops
  this.outboundCustomTimes = [];
  this.returnCustomTimes = [];
  this.loadingCount = 0; // pour l'indicateur de chargement de la carte
    this.lastGeocodedValues = {}; // évite de géocoder deux fois la même valeur
    // Debounce timers pour les recherches d'adresses
    this.searchDebounceTimers = {};
    // Flag pour ignorer les changements programmatiques d'input
    this.ignoreNextInputEvent = {};
    // Flag pour indiquer qu'une adresse a été sélectionnée (ne pas afficher de nouvelles suggestions)
    this.addressSelected = {};
    // Filtrage côté "Trouver": activé uniquement après clic sur Rechercher
  this.findFilterActive = false;
    
    // État de la page de recherche: 'outbound' (aller) ou 'return' (retour)
    this.findSearchPage = 'outbound';
    
    // Offre sélectionnée pour l'aller (stockée avant de passer au retour)
    this.selectedOutboundOffer = null;
    
    // Offre sélectionnée pour le retour
    this.selectedReturnOffer = null;
    
    // Réservations actuelles de l'utilisateur (pour vérifier les doublons)
    this.myReservations = [];
    
    // SUPPRIMÉ: Les clés API ne doivent PAS être dans le frontend
    // Utilisez l'attribut 'api-url' pour configurer l'URL du backend
    
    // État des champs par onglet pour éviter le partage de valeurs
    this.tabFormState = {
      find: { from: '', to: '', date: '', returnDate: '', seats: '4' },
      offer: { from: '', to: '', date: '', fromTime: '00:00', seats: '4' }
    };
    
    // État de la carte par onglet (marqueurs, coords, tracés)
    this.tabMapState = {
      find: {
        startCoords: null,
        endCoords: null,
        startMarker: null,
        endMarker: null,
        stopCoords: [],
        stopMarkers: [],
        stadiumCoords: null
      },
      offer: {
        startCoords: null,
        endCoords: null,
        startMarker: null,
        endMarker: null,
        stopCoords: [],
        stopMarkers: [],
        stadiumCoords: null
      },
      mine: {
        startCoords: null,
        endCoords: null,
        startMarker: null,
        endMarker: null,
        stopCoords: [],
        stopMarkers: [],
        stadiumCoords: null
      }
    };

    // Données calendrier/équipes pour préremplir en fonction du prochain match
    this.yamlData = null;           // contenu de teams.yaml
    this.selectedTeam = null;       // équipe sélectionnée (teams.yaml selection[0].team)
    this.orgIdIndex = new Map();    // index: api_football_org_team_id -> entrée YAML
    this.scheduleMatches = [];      // matches du calendrier
    this.nextMatch = null;          // prochain match normalisé
  this.stadiumCoords = null;      // coordonnées du stade du prochain match (toujours utilisées pour le rayon)
  // Contraintes basées sur le match
  this.matchDateStr = null;
  this.matchStartHHMM = null;
  this.matchMinReturnHHMM = null;
  // Suggestions: cache et panneau flottant
  this.featureCache = new Map(); // label -> [lon,lat]
  this.currentSuggestionPanel = null; // élément DOM du panneau
  this.currentSuggestionAnchor = null; // input associé

  // Rayon de recherche dynamique (défaut 3 km)
  this.searchRadiusMeters = 3000;
  // État de progression du flux Offer (true après confirmation effective)
  this.offerConfirmed = false;
  // Étape du wizard Offer: 1=formulaire, 2=sélection trajet aller, 3=sélection trajet retour (si activé), 4/3=ajustements, 5/4=récap
  this.offerStep = 1;
  
  // Alternatives de trajet ALLER (nouveau pour page 2)
  this.routeAlternatives = []; // Liste des trajets alternatifs d'OSRM
  this.selectedRouteIndex = null; // Index du trajet sélectionné
  
  // Alternatives de trajet RETOUR (nouveau pour page 3)
  this.routeAlternativesReturn = []; // Liste des trajets alternatifs pour le retour
  this.selectedRouteIndexReturn = null; // Index du trajet retour sélectionné
  this.hasReturnTrip = false; // Boolean si trajet retour activé
  
  // État de la page de sélection de route actuellement affichée
  this.currentRouteSelectionMode = null; // 'outbound' ou 'return'

  // Attributs event (fournis par la page hôte)
  this.eventId = this.getAttribute('event-id') || '';
  this.eventName = this.getAttribute('event-name') || '';
  this.eventLocation = this.getAttribute('event-location') || '';
  this.eventDate = this.getAttribute('event-date') || '';
  this.eventTime = this.getAttribute('event-time') || '';

  }

  // Helper pour vérifier si on est en mode récurrent
  isRecurrentMode() {
    return this.widgetMode === 'recurrent';
  }

  // Helper pour vérifier si on est en mode RSE (comportement séparé du récurrent)
  isRseMode() {
    return this.widgetMode === 'rse';
  }

  // Helper pour vérifier si on est en mode récurrent OU RSE (comportement commun)
  isRecurrentOrRseMode() {
    return this.widgetMode === 'recurrent' || this.widgetMode === 'rse';
  }

  // Helpers pour manipulation de couleurs
  _hexToRgb(hex) {
    const h = hex.replace('#', '');
    const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h;
    const bigint = parseInt(full, 16);
    return { r: (bigint >> 16) & 255, g: (bigint >> 8) & 255, b: bigint & 255 };
  }

  _hexToRgba(hex, a) {
    const { r, g, b } = this._hexToRgb(hex);
    return `rgba(${r},${g},${b},${a})`;
  }

  _darkenHex(hex, amount = 0.28) {
    const { r, g, b } = this._hexToRgb(hex);
    const factor = 1 - amount;
    const nr = Math.max(0, Math.min(255, Math.round(r * factor)));
    const ng = Math.max(0, Math.min(255, Math.round(g * factor)));
    const nb = Math.max(0, Math.min(255, Math.round(b * factor)));
    // Générer hex RGB à 6 caractères
    const hexValue = ((nr << 16) + (ng << 8) + nb).toString(16).padStart(6, '0');
    return `#${hexValue}`;
  }

  // Wizard: applique la visibilité selon l'étape Offer
  setOfferStep(step) {
    try {
      const maxStep = this.hasReturnTrip ? 5 : 4;
      const s = Math.max(1, Math.min(maxStep, Number(step) || 1));
      this.offerStep = s;
      this.applyOfferStep();
    } catch(_) {}
  }

  applyOfferStep() {
    try {
      const isOffer = this.activeTab === 'offer';
      
      // En mode RSE, toujours traiter comme "offer"
      if (this.isRseMode() && !isOffer) {
        console.warn('⚠️ Mode RSE détecté mais activeTab n\'est pas "offer", forçage...');
        this.activeTab = 'offer';
      }
      
      const searchCard = this.shadowRoot && this.shadowRoot.querySelector('.search-card');
      const confirmWrapper = this.shadowRoot && this.shadowRoot.getElementById('confirm-trip-wrapper');
      const routeSelectionWrapper = this.shadowRoot && this.shadowRoot.getElementById('route-selection-wrapper');
      const calculateWrapper = this.shadowRoot && this.shadowRoot.getElementById('calculate-btn-wrapper');
      const tripSummary = this.shadowRoot && this.shadowRoot.getElementById('trip-summary');
      const mapBox = this.shadowRoot && this.shadowRoot.getElementById('map-box-container');
  const mapLegend = this.shadowRoot && this.shadowRoot.getElementById('map-legend');
  const wizardBar = this.shadowRoot && this.shadowRoot.getElementById('offer-wizard-bar');
  const pageTitle = this.shadowRoot && this.shadowRoot.getElementById('offer-page-title');
  const backBtn = this.shadowRoot && this.shadowRoot.getElementById('offer-back-btn');
  const step1 = this.shadowRoot && this.shadowRoot.getElementById('offer-step-1');
  const step2 = this.shadowRoot && this.shadowRoot.getElementById('offer-step-2');
  const step3 = this.shadowRoot && this.shadowRoot.getElementById('offer-step-3');
  const step4 = this.shadowRoot && this.shadowRoot.getElementById('offer-step-4');
  const step5 = this.shadowRoot && this.shadowRoot.getElementById('offer-step-5');
  const item1 = this.shadowRoot && this.shadowRoot.getElementById('step-item-1');
  const item2 = this.shadowRoot && this.shadowRoot.getElementById('step-item-2');
  const item3 = this.shadowRoot && this.shadowRoot.getElementById('step-item-3');
  const item4 = this.shadowRoot && this.shadowRoot.getElementById('step-item-4');
  const item5 = this.shadowRoot && this.shadowRoot.getElementById('step-item-5');

      if (!isOffer && !this.isRseMode()) {
        // Ne rien faire si on n'est pas sur l'onglet Offer
        return;
      }

  const step = this.offerStep;
  const hasReturn = this.hasReturnTrip;
  const timelinesWrap = this.shadowRoot && this.shadowRoot.getElementById('timelines-wrap');
  const retCol = this.shadowRoot && this.shadowRoot.getElementById('ret-col');
  const returnCheckboxVis = this.shadowRoot && this.shadowRoot.getElementById('return');
      const show = (el, disp='block') => { if (!el) return; this.animateShow(el, disp); };
      const hide = (el) => { if (!el) return; this.animateHide(el); };

      // Wizard bar visibility and states
      if (wizardBar) {
        wizardBar.style.display = 'flex';
        wizardBar.classList.add('visible');
      }
      if (backBtn) {
        backBtn.style.display = step > 1 ? 'inline-flex' : 'none';
      }
      
      // Adapter la mise en page selon le nombre d'étapes (4 ou 5)
      const wizardSteps = this.shadowRoot && this.shadowRoot.querySelector('.offer-wizard-steps');
      const isRecurrent = this.isRecurrentMode();
      const isRSE = this.isRseMode();
      
      if (wizardSteps) {
        // En mode RSE : seulement 3 étapes
        // En mode récurrent : toujours 4 étapes (pas has-return qui donne 5 colonnes)
        // En mode ponctuel : has-return si checkbox cochée
        if (isRSE) {
          wizardSteps.classList.remove('has-return');
          wizardSteps.classList.add('rse-mode'); // 3 colonnes
        } else if (isRecurrent) {
          wizardSteps.classList.remove('has-return');
          wizardSteps.classList.remove('rse-mode');
        } else if (hasReturn) {
          wizardSteps.classList.add('has-return'); // 5 colonnes
          wizardSteps.classList.remove('rse-mode');
        } else {
          wizardSteps.classList.remove('has-return'); // 4 colonnes
          wizardSteps.classList.remove('rse-mode');
        }
      }
      
      // En mode RSE : affichage dynamique (seulement 3 étapes max)
      if (isRSE) {
        if (item3) item3.style.display = ''; // Montrer step 3 pour le récap
        if (item4) item4.style.display = 'none';
        if (item5) item5.style.display = 'none';
        if (item3) item3.classList.add('last-visible');
        if (item2) item2.classList.remove('last-visible');
      } else {
        // Masquer step 3 (Retour) si pas de trajet retour ET pas en mode récurrent
        if (item3) item3.style.display = (hasReturn || isRecurrent) ? '' : 'none';
        
        // Masquer step 5 en mode récurrent (on n'a que 4 étapes)
        if (item5 && isRecurrent) {
          item5.style.display = 'none';
          // Marquer step 4 comme dernière étape visible pour supprimer la ligne après
          if (item4) item4.classList.add('last-visible');
        } else if (item4) {
          item4.classList.remove('last-visible');
        }
        
        // Retirer la classe last-visible de step 2 en mode non-RSE
        if (item2) item2.classList.remove('last-visible');
      }
      
      // Changer les labels selon le mode
      const step2Label = this.shadowRoot && this.shadowRoot.querySelector('#step-item-2 .step-label');
      const step3Label = this.shadowRoot && this.shadowRoot.querySelector('#step-item-3 .step-label');
      const step4Label = this.shadowRoot && this.shadowRoot.querySelector('#step-item-4 .step-label');
      
      if (isRSE) {
        // Mode RSE : step 2 = "Distance", step 3 = "Récap", step 4 = "Covoit."
        if (step2Label) step2Label.textContent = 'Distance';
        if (step3Label) step3Label.textContent = 'Récap';
        if (step4Label) step4Label.textContent = 'Covoit.';
      } else {
        // Mode normal : step 2 = "Aller", step 3 = "Retour"
        if (step2Label) step2Label.textContent = 'Aller';
        if (step3Label) step3Label.textContent = 'Retour';
        // En mode récurrent : step 4 = "Récap" au lieu de "Ajust."
        if (step4Label && isRecurrent) step4Label.textContent = 'Récap';
        else if (step4Label) step4Label.textContent = 'Ajust.';
      }
      
      // Reset classes
      [step1, step2, step3, step4, step5].forEach(el => { if (!el) return; el.classList.remove('active'); });
      [item1, item2, item3, item4, item5].forEach(el => { if (!el) return; el.classList.remove('active','done'); });
      
      // Logique d'activation des étapes
      // MODE RÉCURRENT: 1=Saisie, 2=Aller, 3=Retour, 4=Récap
      // AVEC retour: 1=Saisie, 2=Aller, 3=Retour, 4=Ajust, 5=Récap
      // SANS retour: 1=Saisie, 2=Aller, 3=Ajust, 4=Récap
      
      if (step === 1) {
        if (item1) item1.classList.add('active');
        if (step1) step1.classList.add('active');
      } else if (step === 2) {
        if (item1) item1.classList.add('done');
        if (item2) item2.classList.add('active');
        if (step2) step2.classList.add('active');
      } else if (step === 3) {
        if (item1) item1.classList.add('done');
        if (item2) item2.classList.add('done');
        if (hasReturn) {
          // Step 3 = Choix retour
          if (item3) item3.classList.add('active');
          if (step3) step3.classList.add('active');
        } else {
          // Step 3 = Ajustements (pas de retour)
          if (item3) item3.classList.add('done'); // skip
          if (item4) item4.classList.add('active');
          if (step4) step4.classList.add('active');
        }
      } else if (step === 4) {
        if (item1) item1.classList.add('done');
        if (item2) item2.classList.add('done');
        if (isRecurrent) {
          // Mode récurrent : Step 4 = Récap
          if (item3) item3.classList.add('done');
          if (item4) item4.classList.add('active');
          if (step4) step4.classList.add('active');
        } else if (hasReturn) {
          // Step 4 = Ajustements (avec retour)
          if (item3) item3.classList.add('done');
          if (item4) item4.classList.add('active');
          if (step4) step4.classList.add('active');
        } else {
          // Step 4 = Récap (sans retour)
          if (item3) item3.classList.add('done');
          if (item4) item4.classList.add('done');
          if (item5) item5.classList.add('active');
          if (step5) step5.classList.add('active');
        }
      } else if (step === 5) {
        // Step 5 = Récap (uniquement avec retour en mode ponctuel)
        if (item1) item1.classList.add('done');
        if (item2) item2.classList.add('done');
        if (item3) item3.classList.add('done');
        if (item4) item4.classList.add('done');
        if (item5) item5.classList.add('active');
        if (step5) step5.classList.add('active');
      }

      // Page title per step (avec logique dynamique)
      if (pageTitle) {
        let title = '';
        if (step === 1) {
          title = ''; // Header intégré dans step1-header
        } else if (step === 2) {
          title = ''; // Header intégré dans route-selection-header
        } else if (step === 3) {
          title = hasReturn ? '' : ''; // Header intégré pour ajustements
        } else if (step === 4) {
          title = hasReturn ? '' : 'Récapitulatif'; // Header intégré pour ajustements
        } else if (step === 5) {
          title = 'Récapitulatif';
        }
        pageTitle.textContent = title;
        pageTitle.style.display = title ? 'block' : 'none';
      }

      // Gestion de l'affichage des sections selon l'étape
      const step1Header = this.shadowRoot && this.shadowRoot.getElementById('step1-header');
      const step4Header = this.shadowRoot && this.shadowRoot.getElementById('step4-header');
      
      if (step === 1) {
        // Page 1: Saisie
        show(searchCard, 'block');
        show(confirmWrapper, 'block');
        show(step1Header, 'block');
        hide(step4Header);
        hide(routeSelectionWrapper);
        hide(calculateWrapper);
        hide(tripSummary);
        hide(mapBox);
        hide(mapLegend);
        hide(timelinesWrap);
        this.setConfirmButtonIdle();
      } else if (step === 2) {
        // Page 2: Choix itinéraire ALLER
        hide(searchCard);
        hide(confirmWrapper);
        hide(step1Header);
        hide(step4Header);
        show(routeSelectionWrapper, 'block');
        show(mapBox, 'block');
        show(mapLegend, 'flex');
        hide(calculateWrapper);
        hide(tripSummary);
        hide(timelinesWrap);
        
        // Mettre à jour le header pour l'aller
        const headerEl = this.shadowRoot.getElementById('route-selection-header');
        if (headerEl) {
          const isRSE = this.isRseMode();
          if (isRSE) {
            headerEl.innerHTML = '<p style="margin: 16px 0 20px 0; text-align: center; font-size: 15px; color: #6B6B6F; font-weight: 600; font-family: ' + this.fontFamily + ';">Voici la distance entre votre domicile et votre travail</p>';
          } else {
            headerEl.innerHTML = '<p style="margin: 16px 0 20px 0; text-align: center; font-size: 15px; color: #6B6B6F; font-weight: 600; font-family: ' + this.fontFamily + ';">Sélectionnez votre itinéraire aller parmi les propositions ci-dessous</p>';
          }
        }
        
        // Définir le mode de sélection
        this.currentRouteSelectionMode = 'outbound';
        
        // Nettoyer la carte des routes retour si elles existent
        if (this.routeAlternativesReturn && this.routeAlternativesReturn.length > 0) {
          this.routeAlternativesReturn.forEach((alt) => {
            const layerId = `route-return-alt-${alt.id}`;
            const sourceId = `route-return-alt-${alt.id}`;
            if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
            if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
          });
        }
        
        // Réafficher toutes les alternatives de l'aller (en cas de retour arrière depuis step 3)
        if (this.routeAlternatives && this.routeAlternatives.length > 0) {
          setTimeout(() => {
            try {
              // Régénérer le HTML des cartes
              const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
              if (routeListEl) {
                routeListEl.innerHTML = this.renderRouteAlternativesHTML();
              }
              // Afficher sur la carte
              this.displayRouteAlternatives();
              this.fitMapToAllAlternatives(false);
              // Attacher les event listeners pour les cartes
              this.attachRouteAlternativeListeners();
            } catch(e) {
              console.error('Erreur lors du réaffichage des alternatives aller:', e);
            }
          }, 100);
        }
        
        setTimeout(() => { try { this.map && this.map.resize(); } catch(_){} }, 50);
      } else if (step === 3 && hasReturn) {
        // Page 3: Choix itinéraire RETOUR (uniquement si retour activé)
        hide(searchCard);
        hide(confirmWrapper);
        hide(step1Header);
        hide(step4Header);
        show(routeSelectionWrapper, 'block');
        show(mapBox, 'block');
        show(mapLegend, 'flex');
        hide(calculateWrapper);
        hide(tripSummary);
        hide(timelinesWrap);
        
        // Mettre à jour le header pour le retour
        const headerEl = this.shadowRoot.getElementById('route-selection-header');
        if (headerEl) {
          headerEl.innerHTML = '<p style="margin: 16px 0 20px 0; text-align: center; font-size: 15px; color: #6B6B6F; font-weight: 600; font-family: ' + this.fontFamily + ';">Sélectionnez votre itinéraire retour parmi les propositions ci-dessous</p>';
        }
        
        // Définir le mode de sélection
        this.currentRouteSelectionMode = 'return';
        
        // Nettoyer la carte des routes aller si elles existent
        if (this.routeAlternatives && this.routeAlternatives.length > 0) {
          this.routeAlternatives.forEach((alt) => {
            const layerId = `route-alt-${alt.id}`;
            const sourceId = `route-alt-${alt.id}`;
            if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
            if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
          });
        }
        
        // Réafficher toutes les alternatives du retour (en cas de retour arrière depuis step 4)
        if (this.routeAlternativesReturn && this.routeAlternativesReturn.length > 0) {
          setTimeout(() => {
            try {
              // Régénérer le HTML des cartes
              const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
              if (routeListEl) {
                routeListEl.innerHTML = this.renderRouteAlternativesHTMLForReturn();
              }
              // Afficher sur la carte
              this.displayReturnRouteAlternatives();
              this.fitMapToAllAlternatives(true);
              // Attacher les event listeners pour les cartes
              this.attachReturnRouteAlternativeListeners();
            } catch(e) {
              console.error('Erreur lors du réaffichage des alternatives retour:', e);
            }
          }, 100);
        }
        
        setTimeout(() => { try { this.map && this.map.resize(); } catch(_){} }, 50);
      } else if (step === 3 && isRSE) {
        // Page 3: Récapitulatif RSE (émissions CO2)
        hide(searchCard);
        hide(confirmWrapper);
        hide(step1Header);
        hide(step4Header);
        hide(routeSelectionWrapper);
        hide(calculateWrapper);
        hide(mapBox);
        hide(mapLegend);
        hide(timelinesWrap);
        show(tripSummary, 'block');
        
        // Générer le récapitulatif RSE
        setTimeout(() => {
          try { this.renderRSESummary(); } catch(e) { console.error('Erreur renderRSESummary:', e); }
        }, 100);
      } else if (step === 3 && !hasReturn) {
        // Page Ajustements (step 3 si pas de retour en mode ponctuel)
        hide(searchCard);
        hide(confirmWrapper);
        hide(step1Header);
        show(step4Header, 'block');
        hide(routeSelectionWrapper);
        show(mapBox, 'block');
        show(mapLegend, 'flex');
        show(calculateWrapper, 'block');
        hide(tripSummary);
        show(timelinesWrap, 'block');
        // Affiche/masque le bloc retour selon le toggle
        if (retCol) {
          retCol.style.display = hasReturn ? '' : 'none';
        }
        // Recalcule les frises
        setTimeout(() => {
          try { this.updateOutboundTimeline(); } catch(_) {}
          try { this.updateReturnTimeline(); } catch(_) {}
        }, 20);
        this.setCalculateButtonIdle();
        setTimeout(() => { try { this.map && this.map.resize(); } catch(_){} }, 50);
      } else if (step === 4) {
        const isRecurrent = this.isRecurrentMode();
        if (isRecurrent) {
          // Mode récurrent : Step 4 = Récapitulatif
          hide(searchCard);
          hide(confirmWrapper);
          hide(step1Header);
          hide(step4Header);
          hide(routeSelectionWrapper);
          hide(calculateWrapper);
          hide(mapBox);
          hide(mapLegend);
          hide(timelinesWrap);
          show(tripSummary, 'block');
        } else if (hasReturn) {
          // Mode ponctuel avec retour : Step 4 = Ajustements
          hide(searchCard);
          hide(confirmWrapper);
          hide(step1Header);
          show(step4Header, 'block');
          hide(routeSelectionWrapper);
          show(mapBox, 'block');
          show(mapLegend, 'flex');
          show(calculateWrapper, 'block');
          hide(tripSummary);
          show(timelinesWrap, 'block');
          if (retCol) {
            retCol.style.display = hasReturn ? '' : 'none';
          }
          setTimeout(() => {
            try { this.updateOutboundTimeline(); } catch(_) {}
            try { this.updateReturnTimeline(); } catch(_) {}
          }, 20);
          this.setCalculateButtonIdle();
          setTimeout(() => { try { this.map && this.map.resize(); } catch(_){} }, 50);
        } else {
          // Mode ponctuel sans retour : Step 4 = Récapitulatif
          hide(searchCard);
          hide(confirmWrapper);
          hide(step1Header);
          hide(step4Header);
          hide(routeSelectionWrapper);
          hide(calculateWrapper);
          hide(mapBox);
          hide(mapLegend);
          hide(timelinesWrap);
          show(tripSummary, 'block');
        }
      } else if (step === 5 && hasReturn) {
        // Page Récapitulatif (step 5 uniquement en mode ponctuel avec retour)
        hide(searchCard);
        hide(confirmWrapper);
        hide(step1Header);
        hide(step4Header);
        hide(routeSelectionWrapper);
        hide(calculateWrapper);
        hide(mapBox);
        hide(mapLegend);
        hide(timelinesWrap);
        show(tripSummary, 'block');
      }
    } catch(_) {}
  }

  // Petites animations d'apparition/disparition
  animateShow(el, display = 'block') {
    try {
      if (!el) return;
      el.style.display = display;
      // Force reflow puis anime
      if (el.classList.contains('fade-slide')) {
        el.classList.remove('visible');
        void el.offsetWidth; // reflow
        el.classList.add('visible');
      }
    } catch(_) {}
  }
  animateHide(el) {
    try {
      if (!el) return;
      if (el.classList.contains('fade-slide')) {
        el.classList.remove('visible');
        setTimeout(() => {
          el.style.display = 'none';
        }, 200);
      } else {
        el.style.display = 'none';
        el.style.setProperty('display', 'none', 'important');
      }
    } catch(_) {}
  }

  // Remet l'UI du bouton Confirmer (étape 1)
  setConfirmButtonIdle() {
    try {
      const btn = this.shadowRoot && this.shadowRoot.getElementById('confirm-trip-btn');
      if (!btn) return;
      btn.disabled = false;
      btn.innerHTML = `
            Confirmer mon trajet
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-left: 8px;">
              <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          `;
    } catch(_) {}
  }
  // Remet l'UI du bouton Calculer (étape 2)
  setCalculateButtonIdle() {
    try {
      const btn = this.shadowRoot && this.shadowRoot.getElementById('calculate-route-btn');
      if (!btn) return;
      btn.disabled = false;
      btn.innerHTML = `
        Calculer l'itinéraire
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-left: 8px;">
          <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      `;
    } catch(_) {}
  }

  // Format HH:MM local
  formatHHMM(dateObj) {
    try {
      return dateObj.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    } catch(_) { return '—'; }
  }
  
  // Format date lisible (ex: "Samedi 15 mars 2025")
  formatReadableDate(dateObj) {
    try {
      return dateObj.toLocaleDateString('fr-FR', { 
        weekday: 'long', 
        day: 'numeric', 
        month: 'long', 
        year: 'numeric' 
      });
    } catch(_) { return '—'; }
  }
  
  // Format HH:MM avec badge de jour si différent de la date de référence
  formatHHMMWithDay(dateObj, referenceDate) {
    try {
      const timeStr = this.formatHHMM(dateObj);
      // Comparer les dates (année, mois, jour)
      const refDay = referenceDate.getDate();
      const refMonth = referenceDate.getMonth();
      const refYear = referenceDate.getFullYear();
      const objDay = dateObj.getDate();
      const objMonth = dateObj.getMonth();
      const objYear = dateObj.getFullYear();
      
      // Calculer la différence en jours
      const dayDiff = Math.round((new Date(objYear, objMonth, objDay).getTime() - new Date(refYear, refMonth, refDay).getTime()) / (1000 * 60 * 60 * 24));
      
      if (dayDiff > 0) {
        return `${timeStr}<span class="tl-day-badge">+${dayDiff}</span>`;
      }
      return timeStr;
    } catch(_) { return '—'; }
  }
  
  // Format heure + date compacte (ex: "14:30" sur ligne 1, "Sam 15 mars" sur ligne 2)
  formatTimeWithCompactDate(dateObj) {
    try {
      const timeStr = this.formatHHMM(dateObj);
      const dateStr = dateObj.toLocaleDateString('fr-FR', { 
        weekday: 'short', 
        day: 'numeric', 
        month: 'short'
      });
      // Retourne HTML avec heure en gros et date en petit dessous
      return `<div class="tl-time-main">${timeStr}</div><div class="tl-date-compact">${dateStr}</div>`;
    } catch(_) { return '—'; }
  }
  
  // Format durée lisible à partir de secondes
  formatDurationSec(sec) {
    try {
      const s = Math.max(0, Math.round(sec || 0));
      const h = Math.floor(s / 3600);
      const m = Math.round((s % 3600) / 60);
      if (h > 0) return `${h} h ${String(m).padStart(2,'0')} min`;
      return `${m} min`;
    } catch(_) { return ''; }
  }
  
  // Génère les options de temps pour un select (incréments de 15 min)
  generateTimeOptions(minTime, currentTime, maxDaysAhead = 2) {
    const options = [];
    const minDate = new Date(minTime);
    const currentDate = new Date(currentTime);
    
    // Arrondir minTime au prochain quart d'heure
    const startTime = new Date(minDate);
    const minutes = startTime.getMinutes();
    const roundedMinutes = Math.ceil(minutes / 15) * 15;
    startTime.setMinutes(roundedMinutes, 0, 0);
    if (roundedMinutes >= 60) {
      startTime.setHours(startTime.getHours() + 1);
      startTime.setMinutes(0, 0, 0);
    }
    
    // Générer des options jusqu'à 2 jours après
    const maxTime = new Date(startTime);
    maxTime.setDate(maxTime.getDate() + maxDaysAhead);
    
    let time = new Date(startTime);
    while (time <= maxTime) {
      const value = time.getTime();
      const hh = String(time.getHours()).padStart(2, '0');
      const mm = String(time.getMinutes()).padStart(2, '0');
      const label = `${hh}:${mm}`;
      
      // Calculer le badge de jour si différent du minTime
      const dayDiff = Math.floor((time.getTime() - minDate.getTime()) / (1000 * 60 * 60 * 24));
      const displayLabel = dayDiff > 0 ? `${label} (+${dayDiff})` : label;
      
      const selected = Math.abs(time.getTime() - currentDate.getTime()) < 60000; // Dans la minute
      options.push({ value, label: displayLabel, selected });
      
      // Incrémenter de 15 minutes
      time = new Date(time.getTime() + 15 * 60 * 1000);
    }
    
    return options;
  }

  // Construit l'itinéraire estimé (heures de passage) pour l'étape 2
  updateOutboundTimeline() {
    try {
      const wrap = this.shadowRoot && this.shadowRoot.getElementById('outbound-timeline');
      if (!wrap) return;
      // Nécessite les jambes OSRM et l'heure de départ
      const legs = Array.isArray(this.outLegs) ? this.outLegs : null;
      if (!legs || !legs.length) { wrap.style.display='none'; wrap.innerHTML=''; return; }
      const dateEl = this.shadowRoot.getElementById('date');
      const fromTimeEl = this.shadowRoot.getElementById('from-time');
      const dateStr = (dateEl && dateEl.value) || '';
      const timeStr = (fromTimeEl && fromTimeEl.value) || '00:00';
      if (!dateStr) { wrap.style.display='none'; wrap.innerHTML=''; return; }
      
      // NOUVEAU: Calculer l'heure de départ à partir de l'heure d'arrivée souhaitée
      // timeStr est maintenant l'heure d'arrivée souhaitée
      const totalDurationSeconds = legs.reduce((sum, l) => sum + (Math.max(0, Number(l && l.duration) || 0)), 0);
      const durationWithMargin = totalDurationSeconds; // Utiliser le temps OSRM brut
      const [arrHH, arrMM] = (timeStr || '00:00').split(':').map(x => parseInt(x,10)||0);
      const [Y, M, D] = dateStr.split('-').map(x => parseInt(x,10)||0);
      const arrivalTime = new Date(Y, (M-1), D, arrHH, arrMM, 0, 0);
      // Calculer l'heure de départ recommandée
      const departureTime = new Date(arrivalTime.getTime() - durationWithMargin * 1000);
      const t0 = departureTime;
      
      // Afficher l'heure de départ calculée dans le header
      const calcDepTimeEl = this.shadowRoot.getElementById('calculated-departure-time');
      if (calcDepTimeEl) {
        const depHH = departureTime.getHours().toString().padStart(2, '0');
        const depMM = departureTime.getMinutes().toString().padStart(2, '0');
        calcDepTimeEl.textContent = `${depHH}:${depMM}`;
      }
      
      // Libellés des points: départ + arrêts + destination
      const fromInput = this.shadowRoot.getElementById('from');
      const toInput = this.shadowRoot.getElementById('to');
      const stopInputs = Array.from(this.shadowRoot.querySelectorAll('input[data-stop-index]'));
      const stops = stopInputs
        .sort((a,b)=> (parseInt(a.dataset.stopIndex,10)||0) - (parseInt(b.dataset.stopIndex,10)||0))
        .map((inp, idx) => (inp.value && inp.value.trim()) || `Étape ${idx+1}`);
      const labels = [ (fromInput && fromInput.value.trim()) || 'Départ', ...stops, (toInput && toInput.value.trim()) || 'Arrivée' ];
      // Calcule les heures cumulées à chaque point (OSRM brut)
      // Garde aussi les temps min (OSRM brut) pour validation d'édition
      const times = [ new Date(t0.getTime()) ];
      const minTimes = [ new Date(t0.getTime()) ]; // temps théorique minimum (OSRM brut)
      const segDurations = legs.map(l => {
        const rawDuration = Math.max(0, Number(l && l.duration) || 0);
        // Utiliser le temps OSRM brut (pas de marge)
        return Math.round(rawDuration);
      });
      const rawSegDurations = legs.map(l => Math.max(0, Number(l && l.duration) || 0));
      
      // Si on a des heures personnalisées stockées, on les utilise
      const customTimes = this.outboundCustomTimes || [];
      
      for (let i=0;i<segDurations.length;i++) {
        const prev = times[i];
        const prevMin = minTimes[i];
        // Pas de temps d'arrêt ajouté
        const stopTime = 0;
        
        // Temps suggéré
        const nextSuggested = new Date(prev.getTime() + (segDurations[i] + stopTime) * 1000);
        // Temps minimum absolu (OSRM brut)
        const nextMin = new Date(prevMin.getTime() + rawSegDurations[i] * 1000);
        
        // Si l'utilisateur a personnalisé cette heure, on la prend (mais on valide qu'elle est >= min)
        if (customTimes[i+1] && customTimes[i+1] >= nextMin.getTime()) {
          times.push(new Date(customTimes[i+1]));
        } else {
          times.push(nextSuggested);
        }
        minTimes.push(nextMin);
      }
      
      // Afficher la date lisible
      const dateDisplay = this.shadowRoot.getElementById('outbound-date');
      if (dateDisplay) {
        dateDisplay.textContent = this.formatReadableDate(t0);
      }
      
      // Génère le HTML
      let html = '';
      for (let i=0;i<labels.length;i++) {
        const kind = i === 0 ? '' : (i === labels.length - 1 ? ' tl-end' : ' tl-stop');
        const timeStr = this.formatTimeWithCompactDate(times[i]);
        
        html += `<div class="tl-row${kind}">
          <div class="tl-time">${timeStr}</div>
          <div class="tl-track"><div class="tl-dot"></div></div>
          <div class="tl-label">${labels[i].replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>
        </div>`;
        if (i < segDurations.length) {
          html += `<div class="tl-seg">
            <div></div><div class="tl-track"></div>
            <div class="tl-duration">${this.formatDurationSec(segDurations[i])}</div>
          </div>`;
        }
      }
      wrap.innerHTML = html;
      wrap.style.display = '';
      
      // Dessiner une colonne verticale continue reliant les points
      setTimeout(() => {
        try {
          let spine = wrap.querySelector('.tl-spine');
          if (!spine) { spine = document.createElement('div'); spine.className = 'tl-spine'; wrap.appendChild(spine); }
          const dots = wrap.querySelectorAll('.tl-dot');
          if (dots.length >= 2) {
            const cardRect = wrap.getBoundingClientRect();
            const firstRect = dots[0].getBoundingClientRect();
            const lastRect = dots[dots.length - 1].getBoundingClientRect();
            const centerX = (firstRect.left - cardRect.left) + (firstRect.width / 2);
            const top = (firstRect.top - cardRect.top) + (firstRect.height / 2);
            const bottom = (lastRect.top - cardRect.top) + (lastRect.height / 2);
            spine.style.left = `${Math.round(centerX - 1)}px`;
            spine.style.top = `${Math.round(top)}px`;
            spine.style.height = `${Math.max(0, Math.round(bottom - top))}px`;
            spine.style.display = '';
          } else if (spine) {
            spine.style.display = 'none';
          }
        } catch(_) {}
      }, 0);
    } catch(_) {}
  }

  // Construit la frise horaire du trajet retour (heures de passage) pour l'étape 2
  updateReturnTimeline() {
    try {
      const wrap = this.shadowRoot && this.shadowRoot.getElementById('return-timeline');
      const retCol = this.shadowRoot && this.shadowRoot.getElementById('ret-col');
      if (!wrap || !retCol) return;
      const legs = Array.isArray(this.retLegs) ? this.retLegs : null;
      const retDateEl = this.shadowRoot.getElementById('return-date-offer');
      const retTimeEl = this.shadowRoot.getElementById('return-time');
      const enabled = (this.shadowRoot.getElementById('return') && this.shadowRoot.getElementById('return').checked);
      
      console.log('🔄 updateReturnTimeline - retLegs:', this.retLegs);
      console.log('🔄 updateReturnTimeline - legs:', legs);
      console.log('🔄 updateReturnTimeline - enabled:', enabled);
      
      if (!enabled || !legs || !legs.length) {
        wrap.innerHTML = '';
        retCol.style.display = 'none';
        return;
      }
      const dateStr = (retDateEl && retDateEl.value) || '';
      const timeStr = (retTimeEl && retTimeEl.value) || '00:00';
      if (!dateStr) { wrap.innerHTML=''; retCol.style.display='none'; return; }
      const [hh, mm] = (timeStr || '00:00').split(':').map(x => parseInt(x,10)||0);
      const [Y, M, D] = dateStr.split('-').map(x => parseInt(x,10)||0);
      const t0 = new Date(Y, (M-1), D, hh, mm, 0, 0);
      // Libellés: départ retour = destination, étapes (inversées), arrivée = origine
      const fromInput = this.shadowRoot.getElementById('from');
      const toInput = this.shadowRoot.getElementById('to');
      const stopInputs = Array.from(this.shadowRoot.querySelectorAll('input[data-stop-index]'));
      const stops = stopInputs
        .sort((a,b)=> (parseInt(a.dataset.stopIndex,10)||0) - (parseInt(b.dataset.stopIndex,10)||0))
        .map((inp, idx) => (inp.value && inp.value.trim()) || `Étape ${idx+1}`)
        .reverse();
      const labels = [ (toInput && toInput.value.trim()) || 'Arrivée', ...stops, (fromInput && fromInput.value.trim()) || 'Départ' ];
      // Heures cumulées (OSRM brut)
      const times = [ new Date(t0.getTime()) ];
      const minTimes = [ new Date(t0.getTime()) ];
      const segDurations = legs.map(l => {
        const rawDuration = Math.max(0, Number(l && l.duration) || 0);
        console.log('🔄 RETURN Leg duration:', l, 'rawDuration:', rawDuration);
        // Utiliser le temps OSRM brut (pas de marge)
        return Math.round(rawDuration);
      });
      const rawSegDurations = legs.map(l => Math.max(0, Number(l && l.duration) || 0));
      
      console.log('🔄 RETURN segDurations:', segDurations);
      console.log('🔄 RETURN rawSegDurations:', rawSegDurations);
      
      const customTimes = this.returnCustomTimes || [];
      
      for (let i=0;i<segDurations.length;i++) {
        const prev = times[i];
        const prevMin = minTimes[i];
        const stopTime = 0; // Pas de temps d'arrêt ajouté
        
        const nextSuggested = new Date(prev.getTime() + (segDurations[i] + stopTime) * 1000);
        const nextMin = new Date(prevMin.getTime() + rawSegDurations[i] * 1000);
        
        if (customTimes[i+1] && customTimes[i+1] >= nextMin.getTime()) {
          times.push(new Date(customTimes[i+1]));
        } else {
          times.push(nextSuggested);
        }
        minTimes.push(nextMin);
      }
      
      // Afficher la date lisible
      const dateDisplay = this.shadowRoot.getElementById('return-date');
      if (dateDisplay) {
        dateDisplay.textContent = this.formatReadableDate(t0);
      }
      
      // HTML
      let html = '';
      for (let i=0;i<labels.length;i++) {
        const kind = i === 0 ? '' : (i === labels.length - 1 ? ' tl-end' : ' tl-stop');
        const timeStr = this.formatTimeWithCompactDate(times[i]);
        
        html += `<div class="tl-row${kind}">
          <div class="tl-time">${timeStr}</div>
          <div class="tl-track"><div class="tl-dot"></div></div>
          <div class="tl-label">${labels[i].replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>
        </div>`;
        if (i < segDurations.length) {
          html += `<div class="tl-seg">
            <div></div><div class="tl-track"></div>
            <div class="tl-duration">${this.formatDurationSec(segDurations[i])}</div>
          </div>`;
        }
      }
      wrap.innerHTML = html;
      retCol.style.display = '';
      // Dessiner une colonne verticale continue reliant les points
      setTimeout(() => {
        try {
          let spine = wrap.querySelector('.tl-spine');
          if (!spine) { spine = document.createElement('div'); spine.className = 'tl-spine'; wrap.appendChild(spine); }
          const dots = wrap.querySelectorAll('.tl-dot');
          if (dots.length >= 2) {
            const cardRect = wrap.getBoundingClientRect();
            const firstRect = dots[0].getBoundingClientRect();
            const lastRect = dots[dots.length - 1].getBoundingClientRect();
            const centerX = (firstRect.left - cardRect.left) + (firstRect.width / 2);
            const top = (firstRect.top - cardRect.top) + (firstRect.height / 2);
            const bottom = (lastRect.top - cardRect.top) + (lastRect.height / 2);
            spine.style.left = `${Math.round(centerX - 1)}px`;
            spine.style.top = `${Math.round(top)}px`;
            spine.style.height = `${Math.max(0, Math.round(bottom - top))}px`;
            spine.style.display = '';
          } else if (spine) {
            spine.style.display = 'none';
          }
        } catch(_) {}
      }, 0);
    } catch(_) {}
  }

  async fetchMyTrips() {
    const wrap = this.shadowRoot.getElementById('my-trips');
    const offersInner = this.shadowRoot.getElementById('my-offers-inner');
    const resInner = this.shadowRoot.getElementById('my-reservations-inner');
  if (!wrap || !offersInner || !resInner) return;
    const uid = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
    if (!uid) {
      offersInner.innerHTML = '<div style="padding:8px;border:1px solid #ccc;background:#fafafa;border-radius:8px;color:#555">Connectez-vous pour voir vos trajets.</div>';
      resInner.innerHTML = '';
      return;
    }
    try {
      // Fetch my offers and my reservations
      const [myOffersRes, myResRes] = await Promise.all([
        fetch(`/api/carpool/mine?user_id=${encodeURIComponent(uid)}`, { credentials: 'include' }),
        fetch(`/api/carpool/reservations?user_id=${encodeURIComponent(uid)}`, { credentials: 'include' })
      ]);
      const myOffers = myOffersRes.ok ? await myOffersRes.json() : [];
      const myReservations = myResRes.ok ? await myResRes.json() : [];
      // Stocker les réservations pour vérifier les doublons
      this.myReservations = myReservations;
      // ✅ Mettre à jour le cache _offers utilisé pour la vérification de doublon
      this._offers = myOffers;
      // Fetch passengers for my offers in one go
      const offerIds = myOffers.map(o => o && o.id).filter(v => v != null);
      let passengersMap = {};
      if (offerIds.length) {
        try {
          const qs = encodeURIComponent(offerIds.join(','));
          const r = await fetch(`/api/carpool/reservations/by-offers?ids=${qs}`, { credentials:'include' });
          if (r.ok) {
            const jj = await r.json();
            passengersMap = (jj && jj.reservations) || {};
            console.log('📦 Réservations reçues du backend:', passengersMap);
          }
        } catch(_) {}
      }
      // Ensure display names/photos for drivers + passengers
      const passengerUids = Object.values(passengersMap)
        .flat()
        .map(p => (p && typeof p === 'object') ? p.user_id : p)
        .filter(Boolean);
      const allUids = [
        ...myOffers.map(o => o && o.user_id),
        ...myReservations.map(o => o && o.user_id),
        ...passengerUids
      ];
      try { await this.ensureProfilesForUids(allUids); } catch(_) {}
      // Render avec colonnes aller/retour pour les offres du conducteur
      offersInner.innerHTML = myOffers.length ? myOffers.map(o => {
          const pid = String(o.id);
          const passengers = Array.isArray(passengersMap[pid]) ? passengersMap[pid] : [];
          console.log(`🔍 Offer ${pid}: ${passengers.length} passengers`, passengers);
          return this.renderOfferWithTripColumns(o, passengers);
        }).join('')
        : '<div style="padding:8px;border:1px solid #ccc;background:#fafafa;border-radius:8px;color:#555">Aucune offre proposée.</div>';
      resInner.innerHTML = myReservations.length ? myReservations.map(o => this.renderOfferCardHTML(o, { mode:'mine-reservations' })).join('')
        : '<div style="padding:8px;border:1px solid #ccc;background:#fafafa;border-radius:8px;color:#555">Aucune réservation.</div>';
      // Attach click handlers to allow selecting an offer to draw its route
      this.attachOfferListHandlersToContainer(offersInner);
      this.attachOfferListHandlersToContainer(resInner);
      // Owner-state on my lists too
      this.applyOwnerStateToOfferCards();
    } catch(e) {
      offersInner.innerHTML = '<div style="padding:8px;border:1px solid #e57373;background:#ffebee;border-radius:8px;color:#c62828">Erreur lors du chargement.</div>';
      resInner.innerHTML = '';
    }
  }

  /**
   * Affiche l'itinéraire avec les étapes et distances
   * Pour le conducteur: montre l'impact des détours sur les horaires et km
   */
  renderDynamicTimeline(offer, passengers, mode) {
    if (mode !== 'mine-offers' || !passengers || passengers.length === 0) return '';
    
    // Filtrer les passagers confirmés
    const confirmedPassengers = passengers.filter(p => p.status === 'confirmed');
    if (confirmedPassengers.length === 0) return '';
    
    console.log('🔍 renderDynamicTimeline - confirmed passengers:', confirmedPassengers);
    
    // Récupérer les infos de route
    const currentRoute = offer.current_route_geometry;
    const originalRoute = offer.route_outbound;
    
    // Calculer distances et durées
    let totalDistanceKm = 0;
    let totalDurationMin = 0;
    let originalDistanceKm = 0;
    let originalDurationMin = 0;
    
    if (currentRoute) {
      try {
        const route = typeof currentRoute === 'string' ? JSON.parse(currentRoute) : currentRoute;
        totalDistanceKm = ((route.distance || 0) / 1000).toFixed(1);
        totalDurationMin = Math.round((route.duration || 0) / 60);
      } catch (e) {}
    }
    
    if (originalRoute) {
      try {
        const route = typeof originalRoute === 'string' ? JSON.parse(originalRoute) : originalRoute;
        originalDistanceKm = ((route.distance || 0) / 1000).toFixed(1);
        originalDurationMin = Math.round((route.duration || 0) / 60);
      } catch (e) {}
    }
    
    const hasDetour = currentRoute && originalRoute && (totalDistanceKm !== originalDistanceKm);
    const extraKm = hasDetour ? (parseFloat(totalDistanceKm) - parseFloat(originalDistanceKm)).toFixed(1) : 0;
    const extraMin = hasDetour ? (totalDurationMin - originalDurationMin) : 0;
    
    // Heures
    const currentDeparture = offer.current_departure_time || offer.datetime;
    const originalDeparture = offer.original_departure_time || offer.datetime;
    const arrivalTime = offer.datetime; // PIVOT IMMUABLE
    
    const timeUsed = offer.time_budget_used || 0;
    const maxTime = offer.max_detour_time || 25;
    const timeRemaining = maxTime - timeUsed;
    
    // Formater les heures
    const formatTime = (dateStr) => {
      if (!dateStr) return '—';
      const d = new Date(dateStr);
      return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    };
    
    // Construire les étapes de la timeline
    const steps = [];
    
    // 1. Départ
    steps.push({
      icon: '🏠',
      label: 'Départ',
      time: formatTime(currentDeparture),
      location: offer.departure,
      color: '#3b82f6'
    });
    
    // 2. Passagers
    confirmedPassengers.forEach((p, idx) => {
      const uid = p.user_id || p.passenger_user_id;
      const displayName = this.getDisplayNameForUid(uid, p);
      console.log(`🔍 renderDynamicTimeline passager ${idx}: uid=${uid}, displayName=${displayName}, p.user_display_name=${p.user_display_name}`);
      steps.push({
        icon: '👤',
        label: displayName,  // Passer p comme objet offer
        time: p.pickup_time ? formatTime(p.pickup_time) : '—',
        location: p.meeting_point_address || p.pickup_address || 'Point de RDV',
        color: '#f59e0b'
      });
    });
    
    // 3. Arrivée (immuable)
    steps.push({
      icon: '🏁',
      label: 'Arrivée',
      time: formatTime(arrivalTime),
      location: offer.destination,
      color: '#10b981',
      isImmutable: true
    });
    
    // HTML des étapes
    const stepsHtml = steps.map((step, index) => {
      const isLast = index === steps.length - 1;
      
      return `
        <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:${isLast ? '0' : '8px'};">
          <div style="display:flex;flex-direction:column;align-items:center;">
            <div style="width:28px;height:28px;border-radius:50%;background:${step.color};display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">${step.icon}</div>
            ${!isLast ? `<div style="width:2px;height:32px;background:#e5e7eb;margin-top:4px;"></div>` : ''}
          </div>
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px;">
              <span style="font-weight:700;color:#111;font-size:13px;font-family:${this.fontFamily};">${step.time}</span>
              ${step.isImmutable ? `<span style="font-size:9px;background:#10b981;color:#fff;padding:2px 6px;border-radius:4px;font-weight:600;">FIXE</span>` : ''}
            </div>
            <div style="font-weight:600;color:#444;font-size:12px;font-family:${this.fontFamily};">${step.label}</div>
            <div style="color:#666;font-size:11px;font-family:${this.fontFamily};">${step.location}</div>
          </div>
        </div>
      `;
    }).join('');
    
    // Header avec stats
    const headerHtml = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
        <div style="font-weight:700;color:#111;font-size:14px;font-family:${this.fontFamily};">
          🗺️ Itinéraire avec ${confirmedPassengers.length} passager${confirmedPassengers.length > 1 ? 's' : ''}
        </div>
        <div style="display:flex;gap:12px;font-size:11px;font-family:${this.fontFamily};">
          <div style="background:#3b82f6;color:#fff;padding:4px 8px;border-radius:6px;font-weight:600;">
            ${totalDistanceKm} km · ${totalDurationMin} min
          </div>
          ${hasDetour ? `
            <div style="background:#f59e0b;color:#fff;padding:4px 8px;border-radius:6px;font-weight:600;">
              +${extraKm} km · +${extraMin} min
            </div>
          ` : ''}
        </div>
      </div>
    `;
    
    // Budget de détour
    const budgetHtml = `
      <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:6px;padding:8px;margin-bottom:12px;font-size:11px;font-family:${this.fontFamily};">
        ⏱️ Temps de détour: <strong style="color:#f59e0b;">${timeUsed}/${maxTime} min utilisés</strong>
        · <span style="color:#10b981;font-weight:600;">${timeRemaining} min restants</span>
      </div>
    `;
    
    return `
      <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin-top:8px;">
        ${headerHtml}
        ${budgetHtml}
        ${stepsHtml}
      </div>
    `;
  }

  /**
   * Affiche une offre avec deux colonnes (aller/retour) pour la gestion conducteur
   * Chaque passager apparaît sur une seule ligne avec ses demandes d'aller et/ou retour
   */
  renderOfferWithTripColumns(offer, allPassengers) {
    const offerId = offer.id;
    const dep = (offer.departure || '').replace(/"/g,'&quot;');
    const dest = (offer.destination || '').replace(/"/g,'&quot;');
    const dt = offer.datetime || '';
    const returnDt = offer.return_datetime || '';
    const currentUserId = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
    
    console.log(`🔍 renderOfferWithTripColumns - offre ${offerId}, ${allPassengers.length} réservations:`, allPassengers);
    console.log(`🔍 Offre complète:`, offer);
    console.log(`🔍 route_outbound:`, offer.route_outbound);
    console.log(`🔍 route_return:`, offer.route_return);
    console.log(`🔍 return_datetime:`, offer.return_datetime);
    
    // Grouper les passagers par user_id pour avoir une ligne par passager
    const passengerGroups = {};
    allPassengers.forEach(p => {
      const puid = p.user_id || p.passenger_user_id;
      if (!passengerGroups[puid]) {
        passengerGroups[puid] = { outbound: null, return: null, user: p };
      }
      const tripType = p.trip_type || 'outbound';
      console.log(`  📋 Passager ${puid}: trip_type=${tripType}, status=${p.status}`);
      passengerGroups[puid][tripType] = p;
    });
    
    console.log('📊 Groupes de passagers:', passengerGroups);
    
    // Places disponibles
    const seatsOutbound = offer.seats_outbound != null ? offer.seats_outbound : offer.seats;
    const seatsReturn = offer.seats_return != null ? offer.seats_return : offer.seats;
    const reservedOutbound = Number(offer.reserved_count_outbound || 0);
    const reservedReturn = Number(offer.reserved_count_return || 0);
    const remainingOutbound = seatsOutbound - reservedOutbound;
    const remainingReturn = seatsReturn - reservedReturn;
    
    // Prix
    const details = offer.details || {};
    const arrRaw = Array.isArray(details.prices?.out) ? details.prices.out : [];
    const firstVal = arrRaw.length ? Number(arrRaw[0]) : null;
    let price = Number.isFinite(firstVal) ? firstVal : null;
    if (!Number.isFinite(price) && details.distanceMeters && Number.isFinite(details.distanceMeters.outbound)) {
      const km = details.distanceMeters.outbound / 1000;
      price = this.computeBasePrice(km, !!details.includeTolls);
    }
    const priceRounded = Number.isFinite(price) ? Math.round(price * 2) / 2 : 0;
    const priceText = priceRounded ? `${priceRounded.toFixed(2).replace('.', ',')} €` : '—';
    
    // Fonction pour formatter les heures
    const formatTime = (dateStr) => {
      if (!dateStr) return '—';
      const d = new Date(dateStr);
      return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    };
    
    // Calculer l'heure de départ de l'aller si pas encore calculée (aucun passager confirmé)
    let outboundDepartureTime = offer.current_departure_time;
    console.log(`🔍 ALLER - current_departure_time de l'offre: ${outboundDepartureTime}`);
    console.log(`🔍 ALLER - return_datetime de l'offre: ${returnDt}`);
    
    if (!outboundDepartureTime && dt && offer.route_outbound) {
      try {
        const routeOutbound = typeof offer.route_outbound === 'string' ? JSON.parse(offer.route_outbound) : offer.route_outbound;
        const durationSec = routeOutbound.duration || 0;
        console.log(`🔍 ALLER - route_outbound:`, routeOutbound);
        console.log(`🔍 ALLER - durée: ${durationSec} sec (${(durationSec/60).toFixed(1)} min)`);
        console.log(`🔍 ALLER - arrivée: ${dt}`);
        const arrivalDate = new Date(dt);
        outboundDepartureTime = new Date(arrivalDate.getTime() - durationSec * 1000);
        console.log(`🔍 ALLER - départ calculé: ${outboundDepartureTime}`);
      } catch (e) {
        console.error('Erreur calcul départ aller:', e);
      }
    }
    
    // Calculer l'heure d'arrivée du retour
    // Priorité : current_return_arrival_time (calculé par backend avec détours)
    // Sinon : calculer depuis return_datetime + route_return.duration
    let returnArrivalTime = null;
    if (offer.current_return_arrival_time) {
      // Utiliser l'heure calculée par le backend (avec ou sans détours)
      returnArrivalTime = new Date(offer.current_return_arrival_time);
      console.log(`🔍 RETOUR - arrivée depuis backend: ${returnArrivalTime}`);
    } else if (returnDt && offer.route_return) {
      // Fallback : calculer depuis la route
      try {
        const routeReturn = typeof offer.route_return === 'string' ? JSON.parse(offer.route_return) : offer.route_return;
        const durationSec = routeReturn.duration || 0;
        console.log(`🔍 RETOUR - route_return:`, routeReturn);
        console.log(`🔍 RETOUR - durée: ${durationSec} sec (${(durationSec/60).toFixed(1)} min)`);
        console.log(`🔍 RETOUR - départ: ${returnDt}`);
        const departDate = new Date(returnDt);
        returnArrivalTime = new Date(departDate.getTime() + durationSec * 1000);
        console.log(`🔍 RETOUR - arrivée calculée: ${returnArrivalTime}`);
      } catch (e) {
        console.error('Erreur calcul arrivée retour:', e);
      }
    }
    
    // Construire timeline verticale pour chaque direction
    const buildVerticalTimeline = (tripType, departureLabel, arrivalLabel, color) => {
      const passengers = allPassengers.filter(p => (p.trip_type || 'outbound') === tripType && p.status === 'confirmed');
      
      const steps = [];
      
      // Pour l'ALLER : dt (datetime) est l'heure d'ARRIVÉE (immuable), current_departure_time est l'heure de départ
      // Pour le RETOUR : returnDt (return_datetime) est l'heure de DÉPART, et on calcule l'arrivée
      let departureTime, arrivalTime;
      
      if (tripType === 'outbound') {
        // ALLER : arrivée fixe, départ calculé
        departureTime = outboundDepartureTime || dt;
        arrivalTime = dt; // Arrivée immuable
      } else {
        // RETOUR : départ fixe, arrivée calculée
        departureTime = returnDt;
        
        // Si l'arrivée retour est stockée (après confirmations avec détours), l'utiliser
        if (offer.current_return_arrival_time) {
          arrivalTime = offer.current_return_arrival_time;
        } else if (passengers.length > 0) {
          // Fallback: approximation depuis le dernier pickup_time
          const sortedPassengers = [...passengers].sort((a, b) => (b.pickup_order || 0) - (a.pickup_order || 0));
          const lastPickupTime = sortedPassengers[0].pickup_time;
          if (lastPickupTime) {
            const lastPickup = new Date(lastPickupTime);
            arrivalTime = new Date(lastPickup.getTime() + 5 * 60 * 1000); // +5 min buffer
          } else {
            arrivalTime = returnArrivalTime;
          }
        } else {
          // Pas de passagers : utiliser la durée de route_return
          arrivalTime = returnArrivalTime;
        }
      }
      
      // 1. Départ
      steps.push({
        icon: '🏠',
        label: 'Départ',
        time: formatTime(departureTime),
        location: departureLabel,
        color: color
      });
      
      // 2. Passagers (triés par pickup_order ou ordre d'ajout)
      passengers.sort((a, b) => (a.pickup_order || 0) - (b.pickup_order || 0));
      passengers.forEach((p) => {
        const uid = p.user_id || p.passenger_user_id;
        const displayName = this.getDisplayNameForUid(uid, p);
        steps.push({
          icon: '👤',
          label: displayName,
          time: formatTime(p.pickup_time),
          location: p.meeting_point_address || p.pickup_address || 'Point de rendez-vous',
          color: '#f59e0b'
        });
      });
      
      // 3. Arrivée
      steps.push({
        icon: '🏁',
        label: 'Arrivée',
        time: formatTime(arrivalTime),
        location: arrivalLabel,
        color: '#10b981'
      });
      
      // Rendu HTML des étapes
      return steps.map((step, index) => {
        const isLast = index === steps.length - 1;
        return `
          <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:${isLast ? '0' : '12px'};">
            <div style="display:flex;flex-direction:column;align-items:center;">
              <div style="width:32px;height:32px;border-radius:50%;background:${step.color};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">${step.icon}</div>
              ${!isLast ? `<div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>` : ''}
            </div>
            <div style="flex:1;">
              <div style="font-weight:700;color:#111;font-size:14px;font-family:${this.fontFamily};margin-bottom:2px;">${step.time}</div>
              <div style="font-weight:600;color:#444;font-size:13px;font-family:${this.fontFamily};margin-bottom:2px;">${step.label}</div>
              <div style="color:#666;font-size:12px;font-family:${this.fontFamily};line-height:1.4;">${step.location}</div>
            </div>
          </div>
        `;
      }).join('');
    };
    
    // Indicateurs de places (carrés verts=libres, gris=réservées)
    let seatIconsOutbound = '';
    for (let i = 0; i < seatsOutbound; i++) {
      const taken = i < reservedOutbound;
      seatIconsOutbound += `<span style="display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:4px;${taken ? 'background:#d1d5db;' : 'background:#10b981;'}"></span>`;
    }
    
    let seatIconsReturn = '';
    for (let i = 0; i < seatsReturn; i++) {
      const taken = i < reservedReturn;
      seatIconsReturn += `<span style="display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:4px;${taken ? 'background:#d1d5db;' : 'background:#10b981;'}"></span>`;
    }
    
    const headerHtml = `
      <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:16px;margin-bottom:16px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;">
          <!-- Colonne Aller -->
          <div>
            <div style="font-size:15px;font-weight:700;color:${this.colorOutbound};margin-bottom:10px;font-family:${this.fontFamily};display:flex;align-items:center;gap:8px;">
              <span>➡️ ALLER</span>
            </div>
            <div style="margin-bottom:12px;">${seatIconsOutbound}</div>
            <div style="background:#fff;border-radius:6px;padding:12px;">
              ${buildVerticalTimeline('outbound', dep, dest, this.colorOutbound)}
            </div>
          </div>
          <!-- Colonne Retour -->
          <div>
            <div style="font-size:15px;font-weight:700;color:${this.colorReturn};margin-bottom:10px;font-family:${this.fontFamily};display:flex;align-items:center;gap:8px;">
              <span>⬅️ RETOUR</span>
            </div>
            <div style="margin-bottom:12px;">${seatIconsReturn}</div>
            <div style="background:#fff;border-radius:6px;padding:12px;">
              ${buildVerticalTimeline('return', dest, dep, this.colorReturn)}
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Tableau des passagers avec colonnes aller/retour
    const canAct = this.isFutureDateTime(dt);
    const hasPassengers = Object.keys(passengerGroups).length > 0;
    
    const passengersHtml = hasPassengers ? `
      <div style="border:1px solid #dee2e6;border-radius:8px;overflow:hidden;">
        <table style="width:100%;border-collapse:collapse;font-family:${this.fontFamily};">
          <thead>
            <tr style="background:#e9ecef;">
              <th style="padding:10px;text-align:left;font-size:13px;font-weight:700;border-bottom:2px solid #dee2e6;">Passager</th>
              <th style="padding:10px;text-align:center;font-size:13px;font-weight:700;border-bottom:2px solid #dee2e6;color:${this.colorOutbound};">➡️ Aller</th>
              <th style="padding:10px;text-align:center;font-size:13px;font-weight:700;border-bottom:2px solid #dee2e6;color:${this.colorReturn};">⬅️ Retour</th>
            </tr>
          </thead>
          <tbody>
            ${Object.entries(passengerGroups).map(([puid, group]) => {
              const url = this.getAvatarUrlForUser(puid);
              const name = this.getDisplayNameForUid(puid, group.user);
              
              const renderTripCell = (reservation, color) => {
                if (!reservation) {
                  return `<td style="padding:10px;text-align:center;background:#f8f9fa;border-bottom:1px solid #dee2e6;">—</td>`;
                }
                
                const status = reservation.status || 'pending';
                const isPending = status === 'pending';
                const isConfirmed = status === 'confirmed';
                
                // Infos supplémentaires
                const pickupAddress = reservation.meeting_point_address || reservation.pickup_address || '';
                const pickupTime = reservation.pickup_time || '';
                
                const statusBadge = isConfirmed 
                  ? `<span style="display:inline-block;background:#10b981;color:#fff;padding:4px 8px;border-radius:6px;font-size:11px;font-weight:600;">✓ Confirmé</span>`
                  : `<span style="display:inline-block;background:#f59e0b;color:#fff;padding:4px 8px;border-radius:6px;font-size:11px;font-weight:600;">⏳ En attente</span>`;
                
                const addressHtml = pickupAddress 
                  ? `<div style="font-size:10px;color:#666;margin-top:4px;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${pickupAddress}">📍 ${pickupAddress}</div>`
                  : '';
                
                const timeHtml = pickupTime 
                  ? `<div style="font-size:10px;color:#666;margin-top:2px;">🕐 ${pickupTime}</div>`
                  : '';
                
                const confirmBtn = canAct && isPending 
                  ? `<button class="btn-confirm-reservation" data-offer-id="${offerId}" data-passenger-id="${puid}" data-trip-type="${reservation.trip_type}" style="background:#10b981;color:#fff;border:none;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:11px;font-weight:600;margin-top:4px;">✓ Confirmer</button>`
                  : '';
                
                const rejectBtn = canAct
                  ? `<button class="btn-reject-reservation" data-offer-id="${offerId}" data-passenger-id="${puid}" data-trip-type="${reservation.trip_type}" style="background:#ef4444;color:#fff;border:none;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:11px;font-weight:600;margin-top:4px;">✗ Annuler</button>`
                  : '';
                
                return `
                  <td style="padding:10px;text-align:center;background:#fff;border-bottom:1px solid #dee2e6;">
                    <div style="display:flex;flex-direction:column;gap:4px;align-items:center;">
                      ${statusBadge}
                      <div style="font-size:11px;color:#10b981;font-weight:600;margin-top:2px;">${priceText}</div>
                      ${addressHtml}
                      ${timeHtml}
                      ${confirmBtn}
                      ${rejectBtn}
                    </div>
                  </td>
                `;
              };
              
              return `
                <tr style="vertical-align:top;">
                  <td style="padding:10px;border-bottom:1px solid #dee2e6;vertical-align:middle;">
                    <div style="display:flex;align-items:center;gap:8px;">
                      <img src="${url}" alt="${name}" style="width:32px;height:32px;border-radius:50%;object-fit:cover;" onerror="this.onerror=null;this.src='/static/images/players/nophoto.png';" />
                      <span style="font-weight:600;font-size:13px;">${name}</span>
                    </div>
                  </td>
                  ${renderTripCell(group.outbound, '#7c3aed')}
                  ${renderTripCell(group.return, '#f97316')}
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    ` : '<div style="padding:12px;border:1px solid #dee2e6;border-radius:8px;background:#f8f9fa;color:#666;text-align:center;font-size:13px;">Aucune demande de réservation</div>';
    
    // Boutons voir l'itinéraire (un ou deux selon aller-retour)
    const hasReturn = offer.return_datetime;
    let viewRouteBtn = '';
    
    if (hasReturn) {
      // Deux boutons : Aller et Retour
      viewRouteBtn = `
        <div style="display:flex;gap:8px;margin-top:12px;">
          <button class="btn-view-route btn-view-my-trip-route" data-offer-id="${offerId}" data-mode="mine-offers" data-trip-type="outbound" style="flex:1;background:${this.colorOutbound};color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-weight:600;font-family:${this.fontFamily};">
            ➡️ Aller
          </button>
          <button class="btn-view-route btn-view-my-trip-route" data-offer-id="${offerId}" data-mode="mine-offers" data-trip-type="return" style="flex:1;background:${this.colorReturn};color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-weight:600;font-family:${this.fontFamily};">
            ⬅️ Retour
          </button>
        </div>
      `;
    } else {
      // Un seul bouton
      viewRouteBtn = `
        <button class="btn-view-route btn-view-my-trip-route" data-offer-id="${offerId}" data-mode="mine-offers" data-trip-type="outbound" style="background:${this.colorOutbound};color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-weight:600;font-family:${this.fontFamily};margin-top:12px;width:100%;">
          📍 Voir l'itinéraire
        </button>
      `;
    }
    
    return `
      <div class="offer-card" data-offer-id="${offerId}" style="padding:16px;border:1px solid #dee2e6;background:#fff;border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,0.06);margin-bottom:16px;">
        ${headerHtml}
        ${passengersHtml}
        ${viewRouteBtn}
      </div>
    `;
  }

  /**
   * Affiche un indicateur du budget de temps de détour (utilisé/restant)
   * Visible uniquement pour le conducteur (mode: 'mine-offers')
   */
  renderDetourBudgetIndicator(offer, mode) {
    if (mode !== 'mine-offers') return '';
    
    const maxDetourTime = offer.max_detour_time || 25;
    const timeUsed = offer.time_budget_used || 0;
    const timeRemaining = maxDetourTime - timeUsed;
    
    // Ne rien afficher si aucun détour accepté
    if (timeUsed === 0) return '';
    
    const percentUsed = (timeUsed / maxDetourTime) * 100;
    const barColor = percentUsed < 50 ? '#10b981' : percentUsed < 80 ? '#f59e0b' : '#ef4444';
    
    return `
      <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:8px 12px;margin:4px 0;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <span style="font-size:12px;font-weight:600;color:#6b7280;font-family:${this.fontFamily};">⏱️ Temps de détour</span>
          <span style="font-size:12px;font-weight:700;color:#111;font-family:${this.fontFamily};">${timeUsed} / ${maxDetourTime} min</span>
        </div>
        <div style="width:100%;height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden;">
          <div style="width:${percentUsed}%;height:100%;background:${barColor};transition:width 0.3s ease;"></div>
        </div>
        <div style="font-size:11px;color:#6b7280;margin-top:4px;font-family:${this.fontFamily};">
          ${timeRemaining > 0 ? `🔋 ${timeRemaining} min disponible pour d'autres passagers` : '⚠️ Budget épuisé'}
        </div>
      </div>
    `;
  }

  

  renderOfferCardHTML(o, opts = {}) {
    const mode = opts.mode || 'default';
    const passengers = Array.isArray(opts.passengers) ? opts.passengers : [];
    const tripType = opts.tripType || o.trip_type || 'outbound'; // Utiliser trip_type de l'offre si disponible
    const dt = o.datetime || '';
    const dep = (o.departure || '').replace(/"/g,'&quot;');
    const dest = (o.destination || '').replace(/"/g,'&quot;');
    const details = o.details || {};
    const stopCount = Array.isArray(details.stops) ? details.stops.length : 0;
    const offerId = o.id != null ? o.id : '';
    // Utiliser seats_outbound/seats_return si disponible, sinon seats général
    const isOutbound = tripType === 'outbound';
    const seats = isOutbound 
      ? (o.seats_outbound != null ? o.seats_outbound : o.seats)
      : (o.seats_return != null ? o.seats_return : o.seats);
    
    // Calculer le nombre de places réservées
    const reserved = isOutbound
      ? Number(o.reserved_count_outbound || o.reserved_count || 0)
      : Number(o.reserved_count_return || 0);
    
    // Utiliser seats_available si fourni par le backend (après déduction des réservations)
    // Sinon calculer avec reserved_count
    let remaining;
    if (o.seats_available != null) {
      // Backend a déjà calculé les places disponibles
      remaining = Number(o.seats_available);
    } else {
      // Fallback: calculer avec reserved_count
      remaining = (Number.isFinite(Number(seats)) ? Number(seats) - reserved : null);
    }
    
    const remainingStr = (remaining != null && remaining >= 0) ? `Places: ${remaining}/${seats}` : `Places: ${seats}`;
    const full = remaining != null && remaining <= 0;
    
    // Debug log pour vérifier le calcul des places
    if (offerId) {
      console.log(`🔍 Offre ${offerId} (${tripType}): ${seats} places total, ${remaining} restantes (seats_available=${o.seats_available})`, o);
    }
    const currentUserId = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
    const isOwner = currentUserId && o.user_id && String(o.user_id) === currentUserId;
    const uid = o.user_id != null ? String(o.user_id) : null;
    const avatarHtml = this.getAvatarHtml(uid);
    const driverName = this.getDisplayNameForUid(uid, o);
    
    // Utiliser l'heure de départ ajustée si des détours ont été confirmés
    const displayTime = o.current_departure_time || dt;
    const departureHtml = this.formatDateTimeFRHTML(displayTime);
    const hasAdjustedTime = o.current_departure_time && o.current_departure_time !== dt;
    
      // price
      let priceText = '';
      let priceRounded = null;
    try {
      const arrRaw = Array.isArray(details.prices?.out) ? details.prices.out : [];
      const firstVal = arrRaw.length ? Number(arrRaw[0]) : null;
      let price = Number.isFinite(firstVal) ? firstVal : null;
      if (!Number.isFinite(price) && details.distanceMeters && Number.isFinite(details.distanceMeters.outbound)) {
        const km = details.distanceMeters.outbound / 1000;
        price = this.computeBasePrice(km, !!details.includeTolls);
      }
        if (Number.isFinite(price)) {
          priceRounded = Math.round(price * 2) / 2;
          priceText = `${priceRounded.toFixed(2).replace('.', ',')} €`;
        } else {
          priceText = '—';
        }
    } catch(_) { priceText = '—'; }
    // seats icons
    let seatIcons = '';
    if (Number.isFinite(Number(seats))) {
      const totalSeats = Number(seats);
      for (let i=0;i<totalSeats;i++) {
        const taken = i < reserved;
        seatIcons += `<span class="seat-icon" aria-hidden="true" style="display:inline-block;width:14px;height:14px;border-radius:3px;margin-right:3px;${taken? 'background:rgba(0,0,0,0.18);' : 'background:#1e8f2e;'}"></span>`;
      }
    }
    // button area depending on mode
    const canCancel = this.isFutureDateTime(dt);
    let leftBtnHtml = '';
    if (mode === 'mine-offers') {
      // Bouton pour voir l'itinéraire
      leftBtnHtml = `<button class="btn-view-route btn-view-my-trip-route" data-offer-id="${offerId}" data-mode="mine-offers" style="background:#3b82f6;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-weight:600;font-family:${this.fontFamily};">📍 Voir l'itinéraire</button>`;
    } else if (mode === 'mine-reservations') {
      const status = (o && o.reservation_status) || 'pending';
      const statusHtml = status === 'confirmed'
        ? `<span class="status-badge status-confirmed">Confirmé</span>`
        : `<span class="status-badge status-pending">En attente de confirmation</span>`;
      const cancelBtnHtml = canCancel ? `<button class="btn-danger btn-cancel-reservation" data-offer-id="${offerId}" style="min-width:86px;">Annuler</button>`
                              : `<button class="btn-reserve" disabled style="min-width:86px;opacity:.7;">Réservé</button>`;
      const viewRouteBtn = `<button class="btn-view-route btn-view-my-trip-route" data-offer-id="${offerId}" data-mode="mine-reservations" style="background:#3b82f6;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-weight:600;font-family:${this.fontFamily};margin-top:8px;">📍 Voir l'itinéraire</button>`;
      leftBtnHtml = `<div class="actions actions-vertical">${statusHtml}${cancelBtnHtml}${viewRouteBtn}</div>`;
    } else {
      const btnText = full ? 'Complet' : 'Réserver';
      const btnDisabled = full;
      leftBtnHtml = `<button class="btn-reserve" data-reserve-offer-id="${offerId}" aria-label="Réserver ce covoiturage" ${btnDisabled ? 'disabled' : ''} style="min-width:86px;">${btnText}</button>`;
    }
    // Passengers section (only on my offers and only if there are any)
    let passengersHtml = '';
    if ((mode === 'mine-offers' || isOwner) && passengers.length) {
      const items = passengers.map(p => {
        const puid = (p && typeof p === 'object') ? (p.user_id || p.passenger_user_id) : p;
        const pstatus = (p && typeof p === 'object' && p.status) ? p.status : 'pending';
        const url = this.getAvatarUrlForUser(puid);
        const name = this.getDisplayNameForUid(puid, p);  // Passer p pour accéder à user_display_name
          const paxPriceHtml = priceText && priceText !== '—' ? `<span class="pax-price" title="Prix par passager" style="margin-right:8px;font-weight:600;color:var(--brand,#1f8f56);font-family:${this.fontFamily};">${priceText}</span>` : '';
        const statusHtml = pstatus === 'confirmed'
          ? `<span class="status-badge status-confirmed">Confirmé</span>`
          : `<button class="btn-pending btn-confirm-reservation" type="button" data-offer-id="${offerId}" data-passenger-id="${puid}">En attente de confirmation</button>`;
        const canAct = this.isFutureDateTime(dt);
        // Ne pas afficher "Confirmer" en mode pending, seulement le label orange + Annuler
        const confirmBtn = '';
        const rejectBtn = canAct
          ? `<button class="btn-reject btn-reject-reservation" data-offer-id="${offerId}" data-passenger-id="${puid}">Annuler</button>`
          : '';
        return `<div class="passenger"><img class="avatar-md" src="${url}" alt="${name}" onerror="this.onerror=null;this.src='/static/images/players/nophoto.png';" /><span>${name}</span><span style="flex:1"></span>${paxPriceHtml}<div class="pax-actions">${statusHtml}${confirmBtn}${rejectBtn}</div></div>`;
      }).join('');
      passengersHtml = `<div class="passengers" aria-label="Passagers ayant réservé">${items}</div>`;
    }
      const rightPriceHtml = (mode === 'mine-offers')
        ? ''
        : `<span class="price-tag" style="font-size:22px;font-weight:800;color: var(--brand);font-family:${this.fontFamily};">${priceText}</span>`;
      // Total row for 'Mes offres'
      const passengerCount = passengers.length;
      let totalHtml = '';
      if ((mode === 'mine-offers' || isOwner) && passengerCount && Number.isFinite(priceRounded)) {
        const total = priceRounded * passengerCount;
        const totalText = `${total.toFixed(2).replace('.', ',')} €`;
        totalHtml = `<div class="total-row" style="display:flex;justify-content:flex-end;margin-top:6px;">
          <span style="font-size:15px;font-weight:700;color:#111;font-family:${this.fontFamily};">Total&nbsp;: <span style="color:var(--brand,#1f8f56);font-weight:800;font-family:${this.fontFamily};">${totalText}</span></span>
        </div>`;
      }
      const footerHasContent = !!leftBtnHtml || !!rightPriceHtml;
      const footerStyle = leftBtnHtml && rightPriceHtml
        ? 'display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:2px;'
        : 'display:flex;align-items:center;justify-content:flex-end;gap:16px;margin-top:2px;';
    return `<div class="offer-card" data-offer-id="${offerId}" style="display:flex;flex-direction:column;gap:8px;padding:12px 14px;border:1px solid #ddd;background:#fff;border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,0.06)">
  <div class="driver-name" style="font-size:16px;font-weight:700;color:#111;margin-bottom:4px;font-family:${this.fontFamily};">${driverName}</div>
      <div class="header-row"><span>${avatarHtml}</span><div style="font-weight:600;color:#222;font-size:15px;line-height:1.2;font-family:${this.fontFamily};">${dep} → ${dest}</div></div>
      <div style="font-size:13px;color:#444;display:flex;flex-direction:column;gap:4px;font-family:${this.fontFamily};">
        <span>Arrivée: ${departureHtml} · ${remainingStr} · Étapes: ${stopCount}</span>
  <span class="seats-row" aria-label="Occupation">${seatIcons}</span>
      </div>
        ${this.renderDynamicTimeline(o, passengers, mode)}
        ${passengersHtml}
        ${totalHtml}
        ${footerHasContent ? `<div style="${footerStyle}">${leftBtnHtml}${rightPriceHtml}</div>` : ''}
    </div>`;
  }
  async onFindSearchClick() {
    try {
      // Mode récurrent: recherche par site et jours
      if (this.isRecurrentMode()) {
        return await this.onFindSearchRecurrent();
      }
      
      // Mode ponctuel: recherche par rayon géographique
      // Active le filtrage et détermine le centre de recherche
      const fromEl = this.shadowRoot.getElementById('from');
      const raw = (fromEl && fromEl.value || '').trim();
      
      console.log('🔍 onFindSearchClick - Adresse saisie:', raw);
      
      // Stocker le nom de la localisation recherchée
      this.searchLocationName = raw || 'Votre recherche';
      
      // Si on a déjà des coords (via sélection), on les utilise; sinon on géocode l'input si présent
      if (!this.startCoords && raw) {
        console.log('🌍 Géocodage de l\'adresse:', raw);
        const c = await this.geocodeAddress(raw);
        console.log('📍 Résultat géocodage:', c);
        if (c) this.startCoords = c;
      }
      // Fallback éventuel: s'appuyer sur les coordonnées du stade si dispo
      if (!this.startCoords && Array.isArray(this.stadiumCoords)) {
        console.log('🏟️ Fallback sur coordonnées stade:', this.stadiumCoords);
        this.startCoords = this.stadiumCoords.slice();
      }
      console.log('📌 Coordonnées finales de recherche:', this.startCoords);
      if (this.startCoords) {
        // Show loading while searching
        const resultsSection = this.shadowRoot.getElementById('find-offers');
        const resultsRegion = this.shadowRoot.getElementById('find-results-region');
        const searchBtn = this.shadowRoot.getElementById('validate');
        
        // Remplacer le contenu du bouton par spinner + texte
        if (searchBtn) {
          searchBtn.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;gap:8px;"><div class="spinner" style="width:16px;height:16px;border-width:2px;border-color:#fff;border-top-color:transparent;"></div><span>Recherche en cours…</span></div>';
        }
        
        if (resultsSection) resultsSection.style.display = 'none';
        if (resultsRegion) resultsRegion.classList.add('is-loading');
        this.searchCenterCoords = this.startCoords.slice();
        this.findFilterActive = true;
        // Réinitialiser les sélections lors d'une nouvelle recherche
        this.selectedOutboundOffer = null;
        this.selectedReturnOffer = null;
        this.findSearchPage = 'outbound';
        try { this.drawSearchRadius(this.searchCenterCoords, this.searchRadiusMeters); } catch(_) {}
        try {
          // Chercher les offres qui passent près du point de recherche
          await this.fetchCarpoolOffersNearPoint(this.searchCenterCoords[0], this.searchCenterCoords[1], this.searchRadiusMeters);
          this.renderFindOffersFiltered();
          // Hide loading, show results
          if (resultsSection) resultsSection.style.display = 'block';
          if (resultsRegion) resultsRegion.classList.remove('is-loading');
          
          // Restaurer le texte du bouton
          if (searchBtn) searchBtn.innerHTML = 'Rechercher';
          
          // Faire défiler vers les onglets Aller/Retour après le rendu
          setTimeout(() => {
            const findOffersSection = this.shadowRoot.getElementById('find-offers');
            if (findOffersSection) {
              findOffersSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
          }, 100);
        } catch(_) {}
      } else {
        alert("Renseignez une adresse de départ pour lancer la recherche.");
      }
    } catch(_) { /* noop */ }
  }
  
  /**
   * Recherche de covoiturages en mode récurrent
   */
  async onFindSearchRecurrent() {
    try {
      const resultsSection = this.shadowRoot.getElementById('recurrent-search-results');
      const resultsRegion = this.shadowRoot.getElementById('recurrent-results-region');
      // Récupérer les paramètres de recherche
      const fromEl = this.shadowRoot.getElementById('from');
      const siteSelector = this.shadowRoot.getElementById('site-selector-find');
      
      const fromAddress = (fromEl && fromEl.value || '').trim();
      const siteId = siteSelector && siteSelector.value;
      
      // Validation
      if (!fromAddress) {
        alert('Veuillez saisir votre adresse de départ');
        return;
      }
      
      if (!siteId) {
        alert('Veuillez sélectionner le site de destination');
        return;
      }
      
      // Montre le chargement seulement après validations
      const searchBtn = this.shadowRoot.getElementById('validate');
      
      // Remplacer le contenu du bouton par spinner + texte
      if (searchBtn) {
        searchBtn.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;gap:8px;"><div class="spinner" style="width:16px;height:16px;border-width:2px;border-color:#fff;border-top-color:transparent;"></div><span>Recherche en cours…</span></div>';
      }
      
      if (resultsSection) resultsSection.style.display = 'none';
      if (resultsRegion) resultsRegion.classList.add('is-loading');
      
      // Géocoder l'adresse de départ si nécessaire
      if (!this.startCoords) {
        console.log('🌍 Géocodage de l\'adresse de départ:', fromAddress);
        const coords = await this.geocodeAddress(fromAddress);
        if (coords) {
          this.startCoords = coords;
        } else {
          alert('Impossible de géocoder l\'adresse de départ');
          if (resultsSection) resultsSection.style.display = 'none';
          const searchBtn = this.shadowRoot.getElementById('validate');
          if (searchBtn) searchBtn.innerHTML = 'Rechercher';
          return;
        }
      }
      
      console.log('🔍 Recherche récurrente:', { 
        fromAddress, 
        fromCoords: this.startCoords, 
        siteId
      });
      
      // Stocker le nom de la localisation de recherche pour l'affichage
      this.searchLocationName = fromAddress;
      
      // Appeler l'API de recherche
      const response = await fetch('/api/v2/offers/recurrent/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          site_id: parseInt(siteId),
          departure_coords: this.startCoords
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Erreur lors de la recherche');
      }
      
      const result = await response.json();
      console.log('✅ Résultats de recherche récurrente:', result);
      
      // Stocker les résultats
      this.recurrentSearchResults = result.offers || [];
      
      // Afficher les résultats
      this.renderRecurrentSearchResults();
      if (resultsSection) resultsSection.style.display = 'block';
      if (resultsRegion) resultsRegion.classList.remove('is-loading');
      
      // Restaurer le texte du bouton
      if (searchBtn) searchBtn.innerHTML = 'Rechercher';
      
      // Afficher les routes sur la carte si des résultats existent
      if (this.recurrentSearchResults.length > 0) {
        this.displayRecurrentRoutesOnMap();
      }
      
      // Scroll vers les résultats
      setTimeout(() => {
        const resultsSection = this.shadowRoot.getElementById('recurrent-search-results');
        if (resultsSection) {
          resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
      
    } catch (error) {
      console.error('❌ Erreur recherche récurrente:', error);
      alert('Erreur lors de la recherche: ' + error.message);
      const resultsSection = this.shadowRoot.getElementById('recurrent-search-results');
      const resultsRegion = this.shadowRoot.getElementById('recurrent-results-region');
      const searchBtn = this.shadowRoot.getElementById('validate');
      
      if (resultsSection) resultsSection.style.display = 'none';
      if (resultsRegion) resultsRegion.classList.remove('is-loading');
      
      // Restaurer le texte du bouton
      if (searchBtn) searchBtn.innerHTML = 'Rechercher';
    }
  }
  
  /**
   * Récupère les jours sélectionnés dans l'onglet Find (mode récurrent)
   * @returns {Array} Liste des jours: ['monday', 'tuesday', ...]
   */
  getSelectedDaysFind() {
    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    const selected = [];
    
    days.forEach(day => {
      const checkbox = this.shadowRoot.getElementById(`day-${day}-find`);
      if (checkbox && checkbox.checked) {
        selected.push(day);
      }
    });
    
    return selected;
  }
  
  /**
   * Affiche les résultats de recherche récurrente
   */
  renderRecurrentSearchResults() {
    const container = this.shadowRoot.getElementById('recurrent-search-results');
    const inner = this.shadowRoot.getElementById('recurrent-search-results-inner');
    
    if (!container || !inner) {
      console.error('Container de résultats non trouvé');
      return;
    }
    
    // Afficher le container
    container.style.display = 'block';
    
    // Vider le contenu
    inner.innerHTML = '';
    
    // Afficher le nombre de résultats
    const count = this.recurrentSearchResults?.length || 0;
    
    if (count === 0) {
      inner.innerHTML = `
        <div style="text-align: center; padding: 40px 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
          <div style="font-size: 48px; margin-bottom: 16px;">🔍</div>
          <h3 style="margin: 0 0 8px; font-size: 18px; font-weight: 700; color: #333;">Aucun covoiturage trouvé</h3>
          <p style="margin: 0; color: #666; font-size: 14px;">Essayez de modifier vos critères de recherche</p>
        </div>
      `;
      return;
    }
    
    // Header avec nombre de résultats
    const header = document.createElement('div');
    header.style.cssText = 'margin-bottom: 16px; text-align: center; background: linear-gradient(135deg, var(--color-outbound-light) 0%, var(--color-outbound-lighter) 100%); border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);';
    header.innerHTML = `
      <h3 style="margin: 0; font-size: 20px; font-weight: 700; color: var(--color-outbound-dark);">
        🚗 ${count} covoiturage${count > 1 ? 's' : ''} trouvé${count > 1 ? 's' : ''}
      </h3>
      <p style="margin: 8px 0 0; font-size: 14px; color: #666;">pour ce site</p>
    `;
    inner.appendChild(header);
    
    // Mapper les jours en français
    const dayNames = {
      monday: 'Lun',
      tuesday: 'Mar',
      wednesday: 'Mer',
      thursday: 'Jeu',
      friday: 'Ven',
      saturday: 'Sam',
      sunday: 'Dim'
    };
    
    const allDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    
    // Afficher chaque offre
    this.recurrentSearchResults.forEach(offer => {
      const card = document.createElement('div');
      card.style.cssText = 'background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); transition: all 0.2s ease;';
      
      // Générer les badges de jours (tous les jours, avec highlight pour les jours actifs)
      const dayBadges = allDays.map(day => {
        const dayLabel = dayNames[day] || day;
        const isActive = offer.days.includes(day);
        const bgColor = isActive ? this.colorOutbound : '#e2e8f0';
        const textColor = isActive ? 'white' : '#94a3b8';
        const fontWeight = isActive ? '700' : '500';
        return `<span style="display: inline-block; padding: 4px 10px; background: ${bgColor}; color: ${textColor}; border-radius: 6px; font-size: 12px; font-weight: ${fontWeight}; margin-right: 4px; margin-bottom: 4px;">${dayLabel}</span>`;
      }).join('');
      
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
          <div style="flex: 1;">
            <div style="font-size: 16px; font-weight: 700; color: #333; margin-bottom: 8px;">
              👤 ${offer.driver_name}
            </div>
            <div style="margin-bottom: 12px;">
              ${dayBadges}
            </div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Places disponibles</div>
            <div style="font-size: 24px; font-weight: 700; color: ${offer.seats_available === 0 ? '#dc2626' : this.colorOutbound};">
              ${offer.seats_available !== undefined ? offer.seats_available : offer.seats}
            </div>
            ${offer.seats_available === 0 ? `
            <div style="font-size: 10px; color: #dc2626; font-weight: 600; margin-top: 4px;">⚠️ COMPLET</div>
            ` : ''}
          </div>
        </div>
        
        <div style="background: #f8fafc; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 2px solid #e2e8f0;">
            <div style="flex: 1;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <div style="color: ${this.colorOutbound}; font-size: 18px;">📍</div>
                <div style="flex: 1;">
                  <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Départ</div>
                  <div style="font-size: 13px; font-weight: 600; color: #1e293b;">${this.searchLocationName || offer.departure}</div>
                </div>
              </div>
              <div style="margin-left: 26px; height: 20px; border-left: 3px solid ${this.colorOutbound}; margin-bottom: 8px;"></div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="color: ${this.colorOutbound}; font-size: 18px;">🏢</div>
                <div style="flex: 1;">
                  <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Arrivée</div>
                  <div style="font-size: 13px; font-weight: 600; color: #1e293b;">${offer.destination}</div>
                </div>
              </div>
            </div>
            <div style="font-size: 11px; color: ${this.colorOutbound}; font-weight: 700; writing-mode: vertical-rl; text-orientation: mixed;">ALLER</div>
          </div>
          
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="flex: 1;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <div style="color: ${this.colorReturn}; font-size: 18px;">🏢</div>
                <div style="flex: 1;">
                  <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Départ</div>
                  <div style="font-size: 13px; font-weight: 600; color: #1e293b;">${offer.destination}</div>
                </div>
              </div>
              <div style="margin-left: 26px; height: 20px; border-left: 3px solid ${this.colorReturn}; margin-bottom: 8px;"></div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="color: ${this.colorReturn}; font-size: 18px;">📍</div>
                <div style="flex: 1;">
                  <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Arrivée</div>
                  <div style="font-size: 13px; font-weight: 600; color: #1e293b;">${this.searchLocationName || offer.departure}</div>
                </div>
              </div>
            </div>
            <div style="font-size: 11px; color: ${this.colorReturn}; font-weight: 700; writing-mode: vertical-rl; text-orientation: mixed;">RETOUR</div>
          </div>
        </div>
        
        ${offer.recommended_meeting_point ? `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 12px; background: linear-gradient(135deg, #d1fae5, #a7f3d0); border-radius: 8px; border: 2px solid #10b981;">
          <div style="font-size: 20px;">✅</div>
          <div style="flex: 1;">
            <div style="font-size: 13px; font-weight: 700; color: #047857; margin-bottom: 4px;">Point de rencontre sans détour !</div>
            <div style="font-size: 12px; color: #065f46;">📍 <strong>${offer.recommended_meeting_point.address}</strong></div>
            <div style="font-size: 11px; color: #065f46; margin-top: 4px; font-style: italic;">Rendez-vous à ce point pour ne pas impacter le temps du conducteur</div>
          </div>
        </div>
        ` : offer.remaining_detour_time !== undefined ? `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 8px; background: #fef3c7; border-radius: 6px;">
          <div style="font-size: 16px;">⏱️</div>
          <div style="font-size: 12px; color: #92400e;">
            Détour restant : <strong>${offer.remaining_detour_time} min</strong> ${offer.detour_time_minutes !== null && offer.detour_time_minutes !== undefined ? `(votre détour : <strong>+${offer.detour_time_minutes} min</strong>)` : ''}
          </div>
        </div>
        ` : ''}
        
        <button 
          data-offer-id="${offer.id}"
          style="width: 100%; background: linear-gradient(135deg, ${this.colorOutbound} 0%, ${this.colorReturn} 100%); color: white; border: none; border-radius: 8px; padding: 12px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.2s ease;"
          onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.15)'"
          onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
          🚗 Demander une place
        </button>
      `;
      
      inner.appendChild(card);
      
      // Ajouter l'event listener au bouton
      const contactBtn = card.querySelector('button');
      if (contactBtn) {
        contactBtn.addEventListener('click', () => {
          // Stocker l'offre sélectionnée pour afficher le point de rencontre
          this.selectedOffer = offer;
          this.showMeetingPointCheckbox(offer);
          this.openReservationModal(offer);
        });
      }
    });
  }
  
  /**
   * Affiche la checkbox du point de rencontre au-dessus de la carte
   */
  showMeetingPointCheckbox(offer) {
    const checkbox = this.shadowRoot.getElementById('meeting-point-checkbox');
    const addressEl = this.shadowRoot.getElementById('meeting-point-address');
    const checkboxInput = this.shadowRoot.getElementById('use-meeting-point');
    
    if (!checkbox || !addressEl || !checkboxInput) return;
    
    if (offer.recommended_meeting_point) {
      checkbox.style.display = 'block';
      addressEl.innerHTML = `📍 <strong>${offer.recommended_meeting_point.address}</strong>`;
      
      // Stocker les coordonnées du point de rencontre
      this.meetingPointCoords = offer.recommended_meeting_point.coords;
      this.meetingPointAddress = offer.recommended_meeting_point.address;
      
      // Event listener pour la checkbox
      checkboxInput.addEventListener('change', (e) => {
        if (e.target.checked) {
          // Utiliser le point de rencontre
          this.useMeetingPoint = true;
          console.log('✅ Point de rencontre sélectionné:', this.meetingPointAddress);
        } else {
          // Ne pas utiliser le point de rencontre (détour classique)
          this.useMeetingPoint = false;
          console.log('❌ Point de rencontre désélectionné');
        }
      });
    } else {
      checkbox.style.display = 'none';
      this.useMeetingPoint = false;
    }
  }
  
  /**
   * Ouvre la modal de réservation pour une offre (récurrente ou ponctuelle)
   */
  openReservationModal(offer) {
    // Créer la modal
    const modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 10000; padding: 20px;';
    
    // Détecter si c'est une offre récurrente (a des jours) ou ponctuelle (a une date)
    const isRecurrent = offer.days && Array.isArray(offer.days) && offer.days.length > 0;
    
    // Pour le mode récurrent : générer les checkboxes pour les jours
    let daySelectionHtml = '';
    if (isRecurrent) {
      const dayNames = {
        monday: 'Lundi',
        tuesday: 'Mardi',
        wednesday: 'Mercredi',
        thursday: 'Jeudi',
        friday: 'Vendredi',
        saturday: 'Samedi',
        sunday: 'Dimanche'
      };
      
      const dayCheckboxes = offer.days.map(day => {
        const dayLabel = dayNames[day] || day;
        return `
          <label style="display: flex; align-items: center; gap: 10px; padding: 12px; background: #f8fafc; border-radius: 8px; cursor: pointer; transition: all 0.2s ease;" 
                 onmouseover="this.style.background='#e0e7ff'" 
                 onmouseout="this.style.background='#f8fafc'">
            <input type="checkbox" name="reservation_days" value="${day}" checked 
                   style="width: 18px; height: 18px; cursor: pointer; accent-color: ${this.colorOutbound};">
            <span style="font-size: 14px; font-weight: 600; color: #1e293b;">${dayLabel}</span>
          </label>
        `;
      }).join('');
      
      daySelectionHtml = `
        <div style="margin-bottom: 20px;">
          <label style="display: block; font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 12px;">
            📅 Jours souhaités
          </label>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${dayCheckboxes}
          </div>
        </div>
      `;
    } else {
      // Mode ponctuel : afficher la date
      let dateLabel = '';
      if (offer.datetime) {
        const date = new Date(offer.datetime);
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        dateLabel = date.toLocaleDateString('fr-FR', options);
      }
      
      daySelectionHtml = dateLabel ? `
        <div style="margin-bottom: 20px;">
          <div style="padding: 14px; background: linear-gradient(135deg, ${this.colorOutbound}15, ${this.colorReturn}15); border: 2px solid ${this.colorOutbound}; border-radius: 12px;">
            <div style="font-size: 13px; color: #64748b; margin-bottom: 4px;">📅 Date du trajet</div>
            <div style="font-size: 15px; font-weight: 700; color: #1e293b;">${dateLabel}</div>
          </div>
        </div>
      ` : '';
    }
    
    modal.innerHTML = `
      <div style="background: white; border-radius: 16px; max-width: 500px; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.3);">
        <div style="padding: 24px; border-bottom: 2px solid #e2e8f0;">
          <h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 700; color: #1e293b;">🚗 Demander une place</h3>
          <p style="margin: 0; font-size: 14px; color: #64748b;">Covoiturage avec ${offer.driver_name}</p>
        </div>
        
        <div style="padding: 24px;">
          <!-- Trajet -->
          <div style="background: linear-gradient(135deg, #fef3c7 0%, #fed7aa 100%); border-radius: 12px; padding: 16px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 12px;">
              <div style="flex: 1;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                  <div style="font-size: 20px;">🏠</div>
                  <div style="flex: 1; font-size: 14px; font-weight: 600; color: #1e293b;">${offer.departure}</div>
                </div>
                <div style="margin-left: 28px; height: 24px; border-left: 3px solid #f97316; margin-bottom: 8px;"></div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <div style="font-size: 20px;">🏢</div>
                  <div style="flex: 1; font-size: 14px; font-weight: 600; color: #1e293b;">${offer.destination}</div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 4px; color: #f97316; font-size: 24px;">
                <div>↕️</div>
              </div>
            </div>
            ${offer.seats_available === 0 ? `
            <div style="margin-top: 12px; padding: 12px; background: #fed7aa; border: 2px solid #f97316; border-radius: 8px;">
              <div style="font-size: 13px; font-weight: 700; color: #9a3412; margin-bottom: 4px;">⚠️ Attention : Aucune place disponible</div>
              <div style="font-size: 12px; color: #9a3412; line-height: 1.4;">
                Ce covoiturage affiche complet sur au moins un jour de la semaine. Votre demande a de grandes chances d'être refusée si vous réservez un jour déjà complet.
              </div>
            </div>
            ` : `
            <div style="margin-top: 12px; padding: 10px; background: rgba(255,255,255,0.5); border-radius: 6px; font-size: 12px; color: #1e293b;">
              🪑 <strong>${offer.seats_available} / ${offer.seats}</strong> places disponibles
            </div>
            `}
          </div>
          
          <!-- Sélection des jours (récurrent) ou affichage de la date (ponctuel) -->
          ${daySelectionHtml}
          
          ${offer.recommended_meeting_point ? `
          <!-- Point de rencontre sans détour -->
          <div style="margin-bottom: 20px;">
            <label style="display: flex; align-items: center; gap: 12px; padding: 14px; background: linear-gradient(135deg, #d1fae5, #a7f3d0); border: 2px solid #10b981; border-radius: 12px; cursor: pointer; transition: all 0.2s ease;" 
                   onmouseover="this.style.borderColor='#059669'" 
                   onmouseout="this.style.borderColor='#10b981'">
              <input type="checkbox" id="use_meeting_point" style="width: 22px; height: 22px; cursor: pointer; accent-color: #10b981;">
              <div style="flex: 1;">
                <div style="font-size: 14px; font-weight: 700; color: #047857; margin-bottom: 4px;">✅ Point de rencontre sans détour</div>
                <div style="font-size: 13px; color: #065f46;">📍 <strong>${offer.recommended_meeting_point.address}</strong></div>
                <div style="font-size: 11px; color: #065f46; margin-top: 6px; font-style: italic;">Cochez pour vous rendre à ce point et ne pas créer de détour pour le conducteur</div>
              </div>
            </label>
          </div>
          ` : ''}
          
          <!-- Point de prise en charge -->
          <div style="margin-bottom: 20px;" id="pickup_section">
            <label style="display: block; font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 8px;">
              📍 Votre point de prise en charge
            </label>
            <div style="background: #f0f9ff; border: 2px solid #3b82f6; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
              <p style="margin: 0; font-size: 13px; color: #1e40af; line-height: 1.5;">
                💡 Cliquez sur la carte ci-dessous pour indiquer où vous souhaitez être pris en charge
              </p>
            </div>
            <div id="pickup_map_container" style="height: 400px; border-radius: 8px; overflow: hidden; border: 2px solid #e2e8f0; margin-bottom: 12px;">
              <div id="pickup_map" style="width: 100%; height: 100%; position: relative;"></div>
            </div>
            <div id="pickup_address_display" style="margin-top: 8px; padding: 10px; background: #f8fafc; border-radius: 6px; font-size: 13px; color: #64748b; display: none;">
              <strong>Adresse sélectionnée :</strong> <span id="pickup_address_text">-</span>
              <div id="detour_status_display" style="margin-top: 8px; display: none;"></div>
            </div>
          </div>
          
          <!-- Informations passager -->
          <div style="margin-bottom: 20px;">
            <label style="display: block; font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 8px;">
              👤 Votre nom
            </label>
            <input type="text" id="passenger_name" placeholder="Jean Dupont" 
                   style="width: 100%; padding: 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; box-sizing: border-box;"
                   onfocus="this.style.borderColor='${this.colorOutbound}'" 
                   onblur="this.style.borderColor='#e2e8f0'">
          </div>
          
          <div style="margin-bottom: 20px;">
            <label style="display: block; font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 8px;">
              📧 Votre email
            </label>
            <input type="email" id="passenger_email" placeholder="jean.dupont@entreprise.com" 
                   style="width: 100%; padding: 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; box-sizing: border-box;"
                   onfocus="this.style.borderColor='${this.colorOutbound}'" 
                   onblur="this.style.borderColor='#e2e8f0'">
          </div>
          
          <div style="margin-bottom: 24px;">
            <label style="display: block; font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 8px;">
              📱 Votre téléphone (optionnel)
            </label>
            <input type="tel" id="passenger_phone" placeholder="06 12 34 56 78" 
                   style="width: 100%; padding: 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; box-sizing: border-box;"
                   onfocus="this.style.borderColor='${this.colorOutbound}'" 
                   onblur="this.style.borderColor='#e2e8f0'">
          </div>
          
          <!-- Info message -->
          <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 12px; border-radius: 8px; margin-bottom: 20px;">
            <p style="margin: 0; font-size: 13px; color: #1e40af; line-height: 1.5;">
              ℹ️ Une demande sera envoyée au conducteur qui pourra l'accepter ou la refuser.
            </p>
          </div>
          
          <!-- Boutons -->
          <div style="display: flex; gap: 12px;">
            <button id="cancel_btn" 
                    style="flex: 1; padding: 12px; background: #f1f5f9; color: #475569; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s ease;"
                    onmouseover="this.style.background='#e2e8f0'" 
                    onmouseout="this.style.background='#f1f5f9'">
              Annuler
            </button>
            <button id="submit_btn" 
                    style="flex: 2; padding: 12px; background: linear-gradient(135deg, ${this.colorOutbound} 0%, ${this.colorReturn} 100%); color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.2s ease;"
                    onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.2)'" 
                    onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
              ✅ Envoyer la demande
            </button>
          </div>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    // Initialiser la mini-carte pour la sélection du point de prise en charge
    let pickupCoords = null;
    let pickupAddress = null;
    let pickupMarker = null; // legacy DOM marker (no longer used when using layers)
    let markersData = null;  // GeoJSON FeatureCollection for map-rendered markers
    let detourOutbound = null;
    let detourReturn = null;
    
    setTimeout(() => {
      const mapContainer = modal.querySelector('#pickup_map');
      if (mapContainer && window.maplibregl) {
        // Normaliser les coordonnées (convertir {lat, lon} en [lon, lat] si nécessaire)
        let depCoords = offer.departure_coords;
        let destCoords = offer.destination_coords;
        
        if (depCoords && typeof depCoords === 'object' && !Array.isArray(depCoords)) {
          depCoords = [depCoords.lon, depCoords.lat];
          offer.departure_coords = depCoords; // Mettre à jour pour les futurs accès
        }
        
        if (destCoords && typeof destCoords === 'object' && !Array.isArray(destCoords)) {
          destCoords = [destCoords.lon, destCoords.lat];
          offer.destination_coords = destCoords; // Mettre à jour pour les futurs accès
        }
        
        // Centre initial : point de recherche du passager (Orchies, etc.)
        const centerLon = this.searchCenterCoords ? this.searchCenterCoords[0] : 
          (depCoords && destCoords 
            ? (depCoords[0] + destCoords[0]) / 2
            : 3.057256);
        const centerLat = this.searchCenterCoords ? this.searchCenterCoords[1] :
          (depCoords && destCoords
            ? (depCoords[1] + destCoords[1]) / 2
            : 50.62925);
        
        const pickupMap = new maplibregl.Map({
          container: mapContainer,
          style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
          center: [centerLon, centerLat],
          zoom: 12  // Zoom plus proche sur le point de recherche
        });
        
        pickupMap.addControl(new maplibregl.NavigationControl(), 'top-right');
        
        // Afficher la route et la zone cliquable
        pickupMap.on('load', async () => {
          console.log('🗺️ Carte chargée');
          // S'assurer que la carte connaît la taille réelle du conteneur
          pickupMap.resize();
          
          // Route du conducteur (aller) - Recalculer si absente
          let routeGeometry = null;
          
          // Extraire la géométrie depuis details.route_outbound ou route_outbound direct
          const details = offer.details || {};
          const routeData = details.route_outbound || offer.route_outbound;
          
          if (routeData) {
            if (Array.isArray(routeData) && routeData.length > 0) {
              console.log('✅ Route existante trouvée (format tableau)');
              routeGeometry = routeData;
            } else if (routeData.geometry && Array.isArray(routeData.geometry) && routeData.geometry.length > 0) {
              console.log('✅ Route existante trouvée (format objet avec geometry)');
              routeGeometry = routeData.geometry;
            } else if (routeData.geometry && routeData.geometry.coordinates && Array.isArray(routeData.geometry.coordinates)) {
              console.log('✅ Route existante trouvée (format GeoJSON)');
              routeGeometry = routeData.geometry.coordinates;
            }
          }
          
          if (!routeGeometry && offer.departure_coords && offer.destination_coords) {
            console.log('⚠️ Route absente, recalcul via OSRM...');
            try {
              const coordStr = `${offer.departure_coords[0]},${offer.departure_coords[1]};${offer.destination_coords[0]},${offer.destination_coords[1]}`;
              const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${coordStr}?overview=full&geometries=geojson`;
              const response = await fetch(osrmUrl);
              const data = await response.json();
              
              if (data.routes && data.routes[0] && data.routes[0].geometry) {
                routeGeometry = data.routes[0].geometry.coordinates;
                console.log('✅ Route recalculée avec succès');
              }
            } catch (err) {
              console.error('❌ Erreur recalcul route OSRM:', err);
            }
          }
          
          if (routeGeometry && routeGeometry.length > 0) {
            pickupMap.addSource('offer-route', {
              type: 'geojson',
              data: {
                type: 'Feature',
                geometry: {
                  type: 'LineString',
                  coordinates: routeGeometry
                }
              }
            });

            pickupMap.addLayer({
              id: 'offer-route-line',
              type: 'line',
              source: 'offer-route',
              paint: {
                'line-color': this.colorOutbound,
                'line-width': 4,
                'line-opacity': 0.8
              }
            });

            // === ZONE CLIQUABLE : Projection + Budget temps ===
            try {
              // 1. Projeter le point de recherche sur la route
              if (this.searchCenterCoords && this.searchRadiusMeters) {
                const projectedIdx = this.findNearestPointOnRoute(this.searchCenterCoords, routeGeometry);
                const projectedPoint = routeGeometry[projectedIdx];

                // 2. Calculer le rayon du cercle vert basé sur remaining_detour_time
                const maxDetourMin = offer.remaining_detour_time !== undefined ? offer.remaining_detour_time : (offer.max_detour_time || 10);
                const avgSpeedKmH = 50; // vitesse moyenne urbaine
                const projectionRadiusKm = avgSpeedKmH * (maxDetourMin / 60) * 0.5 * 0.3;
                const projectionRadiusM = projectionRadiusKm * 1000;

                // 3. Créer le cercle vert (autour du point projeté)
                const projectionCircle = this.createCirclePolygon(projectedPoint, projectionRadiusM);

                // 4. Créer le cercle bleu (autour de la recherche du passager)
                const searchCircle = this.createCirclePolygon(this.searchCenterCoords, this.searchRadiusMeters);

                // 5. Calculer l'intersection = zone cliquable
                const intersection = this.calculatePolygonIntersection(projectionCircle.geometry, searchCircle.geometry);

                // Afficher le cercle vert
                pickupMap.addSource('projection-circle', {
                  type: 'geojson',
                  data: projectionCircle
                });

                pickupMap.addLayer({
                  id: 'projection-circle-fill',
                  type: 'fill',
                  source: 'projection-circle',
                  paint: {
                    'fill-color': '#22c55e',
                    'fill-opacity': 0.15
                  }
                });

                pickupMap.addLayer({
                  id: 'projection-circle-outline',
                  type: 'line',
                  source: 'projection-circle',
                  paint: {
                    'line-color': '#22c55e',
                    'line-width': 2,
                    'line-dasharray': [2, 2]
                  }
                });

                // Afficher le cercle bleu
                pickupMap.addSource('search-circle', {
                  type: 'geojson',
                  data: searchCircle
                });

                pickupMap.addLayer({
                  id: 'search-circle-fill',
                  type: 'fill',
                  source: 'search-circle',
                  paint: {
                    'fill-color': '#3b82f6',
                    'fill-opacity': 0.1
                  }
                });

                pickupMap.addLayer({
                  id: 'search-circle-outline',
                  type: 'line',
                  source: 'search-circle',
                  paint: {
                    'line-color': '#3b82f6',
                    'line-width': 2,
                    'line-dasharray': [4, 4]
                  }
                });

                // Afficher l'intersection (zone cliquable)
                if (intersection && intersection.coordinates && intersection.coordinates.length > 0) {
                  pickupMap.addSource('clickable-zone', {
                    type: 'geojson',
                    data: {
                      type: 'Feature',
                      geometry: intersection
                    }
                  });

                  pickupMap.addLayer({
                    id: 'clickable-zone-fill',
                    type: 'fill',
                    source: 'clickable-zone',
                    paint: {
                      'fill-color': '#10b981',
                      'fill-opacity': 0.3
                    }
                  });

                  pickupMap.addLayer({
                    id: 'clickable-zone-outline',
                    type: 'line',
                    source: 'clickable-zone',
                    paint: {
                      'line-color': '#10b981',
                      'line-width': 3
                    }
                  });

                  console.log('✅ Zone cliquable affichée (intersection cercle vert + bleu)');
                }
              }
            } catch (e) {
              console.warn('Erreur zone cliquable:', e);
            }
          }
          
          // === MARQUEURS (rendus via layers symbol avec pins) ===
          try {
            const features = [];
            if (offer.departure_coords && Array.isArray(offer.departure_coords)) {
              features.push({
                type: 'Feature',
                properties: { type: 'departure' },
                geometry: { type: 'Point', coordinates: offer.departure_coords }
              });
            }
            if (offer.destination_coords && Array.isArray(offer.destination_coords)) {
              features.push({
                type: 'Feature',
                properties: { type: 'destination' },
                geometry: { type: 'Point', coordinates: offer.destination_coords }
              });
            }
            markersData = { type: 'FeatureCollection', features };
            
            if (pickupMap.getSource('reservation-markers')) {
              ['marker-search','marker-departure','marker-destination','marker-pickup','marker-pin-departure','marker-pin-destination','marker-pin-pickup']
                .forEach(id => { if (pickupMap.getLayer(id)) { try { pickupMap.removeLayer(id); } catch(_){} } });
              pickupMap.removeSource('reservation-markers');
            }
            
            pickupMap.addSource('reservation-markers', {
              type: 'geojson',
              data: markersData
            });
            // Charger des icônes SVG en data URL puis ajouter les layers symbol
            const svgPinDataURL = (hex) => {
              // Higher-res, bottom-anchored pin with white stroke and subtle shadow
              const svg = `
<svg xmlns='http://www.w3.org/2000/svg' width='64' height='80' viewBox='0 0 24 32'>
  <ellipse cx='12' cy='30.5' rx='4.2' ry='1.8' fill='#000' opacity='0.18'/>
  <path d='M12 1C6.7 1 2.4 5.2 2.4 10.4c0 7.7 9.1 18.8 9.6 18.8s9.6-11.1 9.6-18.8C21.6 5.2 17.3 1 12 1z' fill='${hex}' stroke='white' stroke-width='1.3'/>
  <circle cx='12' cy='10.2' r='3.4' fill='white'/>
  <circle cx='12' cy='10.2' r='2.1' fill='${hex}' opacity='0.3'/>
</svg>`;
              return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
            };

            const loadImage = (id, color) => new Promise((resolve, reject) => {
              const img = new Image(64, 80);
              img.onload = () => { try { pickupMap.addImage(id, img, { pixelRatio: 3 }); resolve(); } catch (e) { resolve(); } };
              img.onerror = reject;
              img.src = svgPinDataURL(color);
            });

            Promise.all([
              loadImage('pin-violet', '#7c3aed'),
              loadImage('pin-orange', '#f97316'),
              loadImage('pin-blue', '#3b82f6')
            ]).then(() => {
              // departure (violet pin)
              pickupMap.addLayer({
                id: 'marker-pin-departure',
                type: 'symbol',
                source: 'reservation-markers',
                filter: ['==', ['get', 'type'], 'departure'],
                layout: {
                  'icon-image': 'pin-violet',
                  'icon-size': 0.9,
                  'icon-anchor': 'bottom',
                  'icon-allow-overlap': true
                }
              });
              // destination (orange pin)
              pickupMap.addLayer({
                id: 'marker-pin-destination',
                type: 'symbol',
                source: 'reservation-markers',
                filter: ['==', ['get', 'type'], 'destination'],
                layout: {
                  'icon-image': 'pin-orange',
                  'icon-size': 0.92,
                  'icon-anchor': 'bottom',
                  'icon-allow-overlap': true
                }
              });
              // pickup clicked (blue pin)
              pickupMap.addLayer({
                id: 'marker-pin-pickup',
                type: 'symbol',
                source: 'reservation-markers',
                filter: ['==', ['get', 'type'], 'pickup'],
                layout: {
                  'icon-image': 'pin-blue',
                  'icon-size': 0.95,
                  'icon-anchor': 'bottom',
                  'icon-allow-overlap': true
                }
              });
              console.log('✅ Pins ajoutés (violet départ, orange arrivée, bleu pickup)');
            }).catch(err => console.warn('Erreur chargement pins:', err));
          } catch (e) {
            console.warn('Erreur ajout markers via layers:', e);
          }
          
          // === MARQUEURS via layers (ajoutés ci-dessous) ===
          
          // === GÉRER LE CLIC SUR LA CARTE (DANS LE CALLBACK LOAD) ===
          const onMapClick = async (e) => {
            console.log('🖱️ Clic détecté à:', e.lngLat);
            
            const coords = e.lngLat;
            const clickedCoords = [coords.lng, coords.lat];
            
            // Afficher un loader
            const addressDisplay = modal.querySelector('#pickup_address_display');
            const addressText = modal.querySelector('#pickup_address_text');
            const detourStatus = modal.querySelector('#detour_status_display');
            addressDisplay.style.display = 'block';
            addressText.innerHTML = '<em style="color: #94a3b8;">🔍 Recherche de l\'adresse...</em>';
            if (detourStatus) detourStatus.style.display = 'none';
            
            // Reverse geocoding pour obtenir l'adresse et snap au point le plus proche
            try {
              const reverseUrl = `https://api-adresse.data.gouv.fr/reverse/?lon=${clickedCoords[0]}&lat=${clickedCoords[1]}`;
              const response = await fetch(reverseUrl);
              
              if (response.ok) {
                const data = await response.json();
                if (data.features && data.features.length > 0) {
                  const feat = data.features[0];
                  pickupAddress = feat.properties.label;
                  // Snap au point de l'adresse la plus proche
                  const snapped = feat.geometry && feat.geometry.coordinates ? feat.geometry.coordinates : clickedCoords;
                  pickupCoords = snapped;
                  addressText.innerHTML = `<strong>📍 ${pickupAddress}</strong>`;
                  
                  // Mettre à jour le pin pickup à la position snappée
                  try {
                    if (!markersData) markersData = { type: 'FeatureCollection', features: [] };
                    markersData.features = markersData.features.filter(f => f.properties && f.properties.type !== 'pickup');
                    markersData.features.push({
                      type: 'Feature',
                      properties: { type: 'pickup' },
                      geometry: { type: 'Point', coordinates: pickupCoords }
                    });
                    const src = pickupMap.getSource('reservation-markers');
                    if (src) src.setData(markersData);
                  } catch (e1) {
                    console.warn('Maj pickup layer failed:', e1);
                  }
                  
                  // === CALCULER LE DÉTOUR ET AFFICHER LA NOUVELLE ROUTE ===
                  try {
                    // Nettoyer ancienne route avec détour
                    if (pickupMap.getLayer('offer-route-detour')) pickupMap.removeLayer('offer-route-detour');
                    if (pickupMap.getSource('offer-route-detour')) pickupMap.removeSource('offer-route-detour');
                    
                    // 1) Récupérer la durée directe depuis offer.route_outbound
                    let directDurationMin = null;
                    if (offer.route_outbound && typeof offer.route_outbound === 'object' && Number.isFinite(offer.route_outbound.duration)) {
                      directDurationMin = Math.round(offer.route_outbound.duration / 60);
                    }
                    
                    // 2) Calculer la route avec détour : départ → pickup → destination
                    const coordStrDetour = `${offer.departure_coords[0]},${offer.departure_coords[1]};${pickupCoords[0]},${pickupCoords[1]};${offer.destination_coords[0]},${offer.destination_coords[1]}`;
                    const detourUrl = `https://router.project-osrm.org/route/v1/driving/${coordStrDetour}?overview=full&geometries=geojson`;
                    
                    addressText.innerHTML = `<strong>📍 ${pickupAddress}</strong><br><em style="color: #94a3b8;">⏳ Calcul du détour...</em>`;
                    
                    const detourRes = await fetch(detourUrl);
                    const detourJson = await detourRes.json();
                    
                    if (detourJson && detourJson.code === 'Ok' && detourJson.routes && detourJson.routes[0]) {
                      const detourRoute = detourJson.routes[0];
                      const detourDurationMin = Math.round(detourRoute.duration / 60);
                      
                      // Si pas de durée directe, la calculer
                      if (directDurationMin == null) {
                        const directStr = `${offer.departure_coords[0]},${offer.departure_coords[1]};${offer.destination_coords[0]},${offer.destination_coords[1]}`;
                        const directUrl = `https://router.project-osrm.org/route/v1/driving/${directStr}?overview=false`;
                        const directRes = await fetch(directUrl);
                        const directJson = await directRes.json();
                        if (directJson && directJson.code === 'Ok' && directJson.routes && directJson.routes[0]) {
                          directDurationMin = Math.round(directJson.routes[0].duration / 60);
                        }
                      }
                      
                      // Calculer le temps de détour
                      const extraMin = directDurationMin != null ? detourDurationMin - directDurationMin : null;
                      const maxMin = offer.remaining_detour_time !== undefined ? offer.remaining_detour_time : (offer.max_detour_time || 10);
                      const isOk = extraMin != null && extraMin <= maxMin;
                      
                      // Stocker pour la soumission
                      detourOutbound = extraMin;
                      
                      // Afficher la route avec détour en VERT si OK, ROUGE sinon (DERRIÈRE la route violette)
                      const routeColor = isOk ? '#10b981' : '#ef4444';
                      const detourGeo = { type: 'Feature', geometry: detourRoute.geometry };
                      pickupMap.addSource('offer-route-detour', {
                        type: 'geojson',
                        data: detourGeo
                      });
                      // Insérer AVANT la couche 'offer-route-line' pour être en arrière-plan
                      pickupMap.addLayer({
                        id: 'offer-route-detour',
                        type: 'line',
                        source: 'offer-route-detour',
                        paint: {
                          'line-color': routeColor,
                          'line-width': 5,
                          'line-opacity': 0.9
                        }
                      }, 'offer-route-line');
                      
                      // Afficher le badge vert/rouge
                      addressText.innerHTML = `<strong>📍 ${pickupAddress}</strong>`;
                      if (detourStatus && extraMin != null) {
                        detourStatus.style.display = 'block';
                        detourStatus.innerHTML = `
                          <span style="display:inline-block;padding:6px 10px;border-radius:999px;font-weight:700;font-size:12px;color:#fff;background:${isOk ? '#10b981' : '#ef4444'};">
                            ${isOk ? '✅ Détour possible' : '❌ Détour trop long'} · +${extraMin} min (max ${maxMin} min)
                          </span>`;
                      }
                      
                      console.log(`✅ Route avec détour affichée (${isOk ? 'VERT' : 'ROUGE'}) - Détour: +${extraMin} min / ${maxMin} max`);
                    }
                  } catch (e2) {
                    console.warn('Erreur calcul/affichage détour:', e2);
                    addressText.innerHTML = `<strong>📍 ${pickupAddress}</strong>`;
                  }
                } else {
                  pickupCoords = clickedCoords;
                  pickupAddress = `${clickedCoords[1].toFixed(5)}, ${clickedCoords[0].toFixed(5)}`;
                  addressText.innerHTML = `<strong>📍 ${pickupAddress}</strong>`;
                }
              } else {
                pickupCoords = clickedCoords;
                pickupAddress = `${clickedCoords[1].toFixed(5)}, ${clickedCoords[0].toFixed(5)}`;
                addressText.innerHTML = `<strong>📍 ${pickupAddress}</strong>`;
              }
            } catch (error) {
              console.error('Erreur reverse geocoding:', error);
              pickupCoords = clickedCoords;
              pickupAddress = `${clickedCoords[1].toFixed(5)}, ${clickedCoords[0].toFixed(5)}`;
              addressText.innerHTML = `<strong>📍 ${pickupAddress}</strong>`;
            }
            
            // Activer le bouton
            const submitBtn = modal.querySelector('#submit_btn');
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
            submitBtn.style.cursor = 'pointer';
            
            console.log('✅ Marqueur placé, adresse:', pickupAddress);
          };
          
          // Attacher le handler de clic
          pickupMap.on('click', onMapClick);
          
        // FIN du callback pickupMap.on('load')
        });
      }
    }, 100);
    
    // Event listener pour la checkbox point de rencontre
    const useMeetingCheckbox = modal.querySelector('#use_meeting_point');
    const pickupSection = modal.querySelector('#pickup_section');
    
    if (useMeetingCheckbox && pickupSection) {
      useMeetingCheckbox.addEventListener('change', (e) => {
        if (e.target.checked) {
          // Masquer la carte, utiliser le point de rencontre
          pickupSection.style.display = 'none';
          pickupCoords = offer.recommended_meeting_point.coords;
          pickupAddress = offer.recommended_meeting_point.address;
          detourOutbound = 0;
          detourReturn = 0;
          console.log('✅ Point de rencontre sélectionné:', pickupAddress);
        } else {
          // Afficher la carte pour sélection manuelle
          pickupSection.style.display = 'block';
          pickupCoords = null;
          pickupAddress = null;
          detourOutbound = null;
          detourReturn = null;
          console.log('❌ Point de rencontre désélectionné, sélection manuelle requise');
        }
      });
    }
    
    // Event listeners
    const cancelBtn = modal.querySelector('#cancel_btn');
    const submitBtn = modal.querySelector('#submit_btn');
    
    cancelBtn.addEventListener('click', () => {
      document.body.removeChild(modal);
    });
    
    submitBtn.addEventListener('click', () => {
      this.submitReservationRequest(offer, modal, pickupCoords, pickupAddress, detourOutbound, detourReturn, isRecurrent);
    });
    
    // Fermer au clic sur le fond
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        document.body.removeChild(modal);
      }
    });
  }
  
  /**
   * Soumet une demande de réservation
   */
  async submitReservationRequest(offer, modal, pickupCoords, pickupAddress, detourOutbound, detourReturn, isRecurrent) {
    // Récupérer les données du formulaire
    const selectedDays = Array.from(modal.querySelectorAll('input[name="reservation_days"]:checked'))
      .map(checkbox => checkbox.value);
    
    const passengerName = modal.querySelector('#passenger_name').value.trim();
    const passengerEmail = modal.querySelector('#passenger_email').value.trim();
    const passengerPhone = modal.querySelector('#passenger_phone').value.trim();
    
    // Vérifier si le point de rencontre est utilisé
    const useMeetingCheckbox = modal.querySelector('#use_meeting_point');
    const useMeetingPoint = useMeetingCheckbox && useMeetingCheckbox.checked;
    
    if (useMeetingPoint && offer.recommended_meeting_point) {
      pickupCoords = offer.recommended_meeting_point.coords;
      pickupAddress = offer.recommended_meeting_point.address;
      detourOutbound = 0;
      detourReturn = 0;
    }
    
    // Validation
    if (isRecurrent && selectedDays.length === 0) {
      alert('⚠️ Veuillez sélectionner au moins un jour');
      return;
    }
    
    if (!pickupCoords || !pickupAddress) {
      alert('⚠️ Veuillez sélectionner votre point de prise en charge sur la carte ou cocher le point de rencontre');
      return;
    }
    
    if (!passengerName) {
      alert('⚠️ Veuillez entrer votre nom');
      return;
    }
    
    if (!passengerEmail || !passengerEmail.includes('@')) {
      alert('⚠️ Veuillez entrer un email valide');
      return;
    }
    
    // Préparer les données selon le type d'offre
    const reservationData = {
      offer_id: offer.id,
      passenger_name: passengerName,
      passenger_email: passengerEmail,
      passenger_phone: passengerPhone || null,
      pickup_coords: pickupCoords,
      pickup_address: pickupAddress,
      detour_outbound: detourOutbound,
      detour_return: detourReturn
    };
    
    // Ajouter days_requested uniquement pour récurrent
    if (isRecurrent) {
      reservationData.days_requested = selectedDays;
    } else {
      // Pour ponctuel, ajouter la date de l'événement au format YYYY-MM-DD
      let eventDate = offer.event_date;
      if (eventDate && typeof eventDate === 'string' && eventDate.includes('GMT')) {
        // Convertir "Sat, 15 Aug 2026 00:00:00 GMT" → "2026-08-15"
        const dateObj = new Date(eventDate);
        eventDate = dateObj.toISOString().split('T')[0];
      }
      reservationData.date = eventDate;  // Le backend attend "date" et non "event_date"
    }
    
    console.log('📤 Demande de réservation:', reservationData);
    
    // Désactiver le bouton pendant l'envoi
    const submitBtn = modal.querySelector('#submit_btn');
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Envoi en cours...';
    
    try {
      // Choisir le bon endpoint selon le type d'offre
      const endpoint = isRecurrent ? '/api/v2/reservations/recurrent' : '/api/v2/reservations/ponctual';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(reservationData)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        document.body.removeChild(modal);
        alert(`✅ Demande envoyée !\n\nUn email a été envoyé à ${offer.driver_name} pour valider votre demande.\nVous recevrez une confirmation par email.`);
      } else {
        alert(`❌ Erreur: ${result.error || 'Une erreur est survenue'}`);
        submitBtn.disabled = false;
        submitBtn.textContent = '✅ Envoyer la demande';
      }
    } catch (error) {
      console.error('Erreur lors de l\'envoi:', error);
      alert('❌ Erreur de connexion. Veuillez réessayer.');
      submitBtn.disabled = false;
      submitBtn.textContent = '✅ Envoyer la demande';
    }
  }
  
  /**
   * Contacter un conducteur de covoiturage récurrent (ancienne méthode)
   */
  contactRecurrentDriver(offer) {
    // Remplacé par openReservationModal
    this.openReservationModal(offer);
  }
  
  /**
   * Affiche les routes des offres récurrentes trouvées sur la carte
   */
  displayRecurrentRoutesOnMap() {
    if (!this.map) {
      console.warn('Carte non initialisée');
      return;
    }
    
    // Rendre la carte visible
    const mapBox = this.shadowRoot.getElementById('map-box-container');
    if (mapBox) {
      mapBox.style.display = 'block';
    }
    
    // Supprimer les couches existantes
    if (this.map.getSource('recurrent-routes')) {
      if (this.map.getLayer('recurrent-routes-outbound')) this.map.removeLayer('recurrent-routes-outbound');
      if (this.map.getLayer('recurrent-routes-return')) this.map.removeLayer('recurrent-routes-return');
      this.map.removeSource('recurrent-routes');
    }
    
    // Construire les features GeoJSON pour toutes les routes
    const features = [];
    const bounds = new maplibregl.LngLatBounds();
    
    this.recurrentSearchResults.forEach((offer, index) => {
      // Route aller
      if (offer.route_outbound && offer.route_outbound.length > 0) {
        features.push({
          type: 'Feature',
          properties: {
            offer_id: offer.id,
            direction: 'outbound',
            driver_name: offer.driver_name,
            color: this.colorOutbound
          },
          geometry: {
            type: 'LineString',
            coordinates: offer.route_outbound
          }
        });
        
        // Étendre les limites
        offer.route_outbound.forEach(coord => bounds.extend(coord));
      }
      
      // Route retour
      if (offer.route_return && offer.route_return.length > 0) {
        features.push({
          type: 'Feature',
          properties: {
            offer_id: offer.id,
            direction: 'return',
            driver_name: offer.driver_name,
            color: this.colorReturn
          },
          geometry: {
            type: 'LineString',
            coordinates: offer.route_return
          }
        });
        
        // Étendre les limites
        offer.route_return.forEach(coord => bounds.extend(coord));
      }
    });
    
    // Ajouter le point de recherche
    if (this.startCoords) {
      bounds.extend(this.startCoords);
    }
    
    // Ajouter la source avec toutes les routes
    this.map.addSource('recurrent-routes', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: features
      }
    });
    
    // Couche pour les routes aller
    this.map.addLayer({
      id: 'recurrent-routes-outbound',
      type: 'line',
      source: 'recurrent-routes',
      filter: ['==', ['get', 'direction'], 'outbound'],
      paint: {
        'line-color': this.colorOutbound,
        'line-width': 4,
        'line-opacity': 0.8
      }
    });
    
    // Couche pour les routes retour
    this.map.addLayer({
      id: 'recurrent-routes-return',
      type: 'line',
      source: 'recurrent-routes',
      filter: ['==', ['get', 'direction'], 'return'],
      paint: {
        'line-color': this.colorReturn,
        'line-width': 4,
        'line-opacity': 0.8,
        'line-dasharray': [2, 2]
      }
    });
    
    // Ajuster la vue de la carte
    if (!bounds.isEmpty()) {
      this.map.fitBounds(bounds, {
        padding: 50,
        maxZoom: 12
      });
    }
    
    console.log(`✅ ${features.length} routes affichées sur la carte`);
    
    // Afficher les points de rencontre recommandés (départ + pickups)
    this.displayRecommendedMeetingPoints();
  }
  
  /**
   * Affiche les points de rencontre recommandés (départ + pickups) sur la carte
   */
  displayRecommendedMeetingPoints() {
    if (!this.map) return;
    
    // Supprimer les marqueurs précédents
    if (this.meetingPointMarkers) {
      this.meetingPointMarkers.forEach(m => m.remove());
    }
    this.meetingPointMarkers = [];
    
    this.recurrentSearchResults.forEach(offer => {
      if (offer.recommended_meeting_point) {
        const coords = offer.recommended_meeting_point.coords;
        const address = offer.recommended_meeting_point.address;
        
        // Créer un marqueur vert avec icône check
        const el = document.createElement('div');
        el.style.cssText = `
          width: 40px;
          height: 40px;
          background: linear-gradient(135deg, #10b981, #059669);
          border: 3px solid white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          color: white;
          cursor: pointer;
          box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
          transition: all 0.2s ease;
        `;
        el.innerHTML = '✓';
        el.title = `Point de rencontre sans détour: ${address}`;
        
        el.addEventListener('mouseenter', () => {
          el.style.transform = 'scale(1.2)';
          el.style.boxShadow = '0 6px 16px rgba(16, 185, 129, 0.6)';
        });
        el.addEventListener('mouseleave', () => {
          el.style.transform = 'scale(1)';
          el.style.boxShadow = '0 4px 12px rgba(16, 185, 129, 0.4)';
        });
        
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat(coords)
          .setPopup(
            new maplibregl.Popup({ offset: 25, closeButton: false })
              .setHTML(`
                <div style="padding: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                  <div style="font-weight: 700; color: #10b981; margin-bottom: 6px; font-size: 13px;">✅ Point de rencontre sans détour</div>
                  <div style="font-size: 12px; color: #374151; line-height: 1.4;">${address}</div>
                  <div style="font-size: 11px; color: #6b7280; margin-top: 6px; font-style: italic;">Pas d'impact sur le temps du conducteur</div>
                </div>
              `)
          )
          .addTo(this.map);
        
        this.meetingPointMarkers.push(marker);
      }
    });
  }

  async connectedCallback() {
    // Initialiser les couleurs depuis les attributs HTML (maintenant disponibles)
    // Nettoyer le format 8 caractères (#RRGGBBaa) vers 6 caractères (#RRGGBB) pour MapLibre
    const cleanHex = (hex) => hex && hex.length === 9 ? hex.substring(0, 7) : hex;
    
    this.colorOutbound = cleanHex(this.getAttribute('color-outbound')) || '#7c3aed';
    this.colorReturn = cleanHex(this.getAttribute('color-return')) || '#f97316';
    this.detourColor = cleanHex(this.getAttribute('detour-color')) || (window.covoiturageConfig && window.covoiturageConfig.detourColor) || (window.carpoolConfig && window.carpoolConfig.detourColor) || '#fbbf24';
    
    // Calculer les variantes de couleur détour
    this.detourColorDark = this._darkenHex(this.detourColor, 0.28);
    this.detourShadow = this._hexToRgba(this.detourColor, 0.18);
    
    console.log('🎨 Couleurs initialisées:', { 
      colorOutbound: this.colorOutbound, 
      colorReturn: this.colorReturn, 
      detourColor: this.detourColor 
    });
    
    // En mode RSE, vérifier le code entreprise avant toute chose
    if (this.widgetMode === 'rse') {
      if (!this.companyCode) {
        this.renderError('❌ Code entreprise manquant', 'Veuillez fournir l\'attribut data-company-code dans le widget.');
        return;
      }
      
      // Valider le code entreprise via l'API
      try {
        const apiUrl = this.API_URL || window.location.origin;
        const response = await fetch(`${apiUrl}/api/v2/companies/verify-code?code=${encodeURIComponent(this.companyCode)}`);
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          this.renderError(
            '❌ Code entreprise invalide', 
            `Le code "${this.companyCode}" n'existe pas ou n'est pas actif.<br><br>` +
            `Contactez votre administrateur ou inscrivez votre entreprise sur <a href="${apiUrl}/signup.html" style="color:#667eea;text-decoration:underline;">cette page</a>.`
          );
          return;
        }
        
        const companyData = await response.json();
        
        // Stocker les données de l'entreprise
        this.companyId = companyData.company_id;
        this.companyName = companyData.company_name;
        this.companySites = companyData.sites || [];
        
        console.log('✅ Code entreprise validé:', {
          code: this.companyCode,
          id: this.companyId,
          name: this.companyName,
          sites: this.companySites.length
        });
        
      } catch (error) {
        console.error('Erreur validation code entreprise:', error);
        this.renderError(
          '❌ Erreur de connexion', 
          'Impossible de vérifier le code entreprise. Veuillez réessayer.'
        );
        return;
      }
      
      // Forcer l'affichage sur "proposer un covoit"
      this.activeTab = 'offer';
    }
    
    // En mode récurrent, résoudre les sites (créer IDs si nécessaire)
    if (this.isRecurrentMode() && this.companyId && this.companySites.length > 0) {
      await this.resolveSites();
    }
    
    // Charge MapLibre puis construit l'UI, ensuite charge YAML + calendrier pour préremplir
    this.injectMapLibreResources().then(async () => {
      await this.ensureYamlLib();
      this.renderUI();
      this.initMap();
      this.bindEvents();
      
      // En mode RSE, activer l'onglet "offer" immédiatement
      if (this.isRseMode()) {
        this.setAttribute('data-active-tab', 'offer'); // Important pour le CSS
        await this.updateTabUI();
        this.setOfferStep(1); // Initialiser l'étape 1 pour s'assurer que applyOfferStep() est appelé
        setTimeout(() => this.initRSETransportCalendar(), 100);
      }

      // Valeurs par défaut immédiates (fallback) = aujourd'hui
      const today = new Date().toISOString().split("T")[0];
      const dateEl = this.shadowRoot.getElementById("date");
      const retDateOfferEl = this.shadowRoot.getElementById("return-date-offer");
      if (dateEl) dateEl.value = today;
      // return-date-offer (offre) : défaut aujourd'hui
      if (retDateOfferEl) retDateOfferEl.value = today;
      // return-date-find (recherche) : pas de défaut, l'utilisateur choisit

      // Préremplir depuis prochain match (date + destination = stade de l'équipe à domicile)
      try { 
        await this.presetFromNextMatch(); 
      } catch(e) { console.warn('carpool: presetFromNextMatch failed', e); }
      
      // Préremplir depuis les attributs event-* (priorité sur le preset du match)
      this.presetFromEventAttributes();
      
      // Sauvegarder l'état initial de l'onglet "offer" APRÈS les presets
      this.saveInitialOfferState();
      
      // Charger les réservations de l'utilisateur si connecté
      try {
        const uid = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
        if (uid) {
          const myResRes = await fetch(`/api/carpool/reservations?user_id=${encodeURIComponent(uid)}`, { credentials: 'include' });
          if (myResRes.ok) {
            this.myReservations = await myResRes.json();
          }
        }
      } catch(e) { console.warn('carpool: failed to load user reservations', e); }
      
      // Charger uniquement le compteur de trajets disponibles
      try {
        await this.loadTripCount();
      } catch(e) { console.warn('carpool: failed to load trip count', e); }
    });
  }

  async ensureYamlLib() {
    if (window.jsyaml) return;
    await new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/js-yaml@4.1.0/dist/js-yaml.min.js';
      s.onload = resolve; s.onerror = reject; document.head.appendChild(s);
    });
  }

  async loadYamlAndSchedule() {
    // Si des attributs event-* sont déjà fournis, pas besoin de charger le YAML/schedule
    if (this.eventId && this.eventName && this.eventDate && this.eventTime) {
      console.log('Event attributes provided, skipping YAML/schedule load');
      // Construire un nextMatch fictif pour compatibilité
      this.nextMatch = {
        id: this.eventId,
        homeTeam: { shortName: this.eventName.split(' vs ')[0] || '' },
        awayTeam: { shortName: this.eventName.split(' vs ')[1]?.split(' (')[0] || '' },
        utcDate: `${this.eventDate}T${this.eventTime}:00Z`,
        competition: { name: this.eventName.match(/\(([^)]+)\)/)?.[1] || '' }
      };
      return;
    }
    
    // Sinon, charger depuis YAML/schedule comme avant
    // 1) Charger teams.yaml
    const yamlUrl = '/static/params/teams.yaml';
    const resp = await fetch(yamlUrl);
    if (!resp.ok) throw new Error('yaml load failed');
    const ytxt = await resp.text();
    this.yamlData = jsyaml.load(ytxt);
    this.selectedTeam = this.yamlData?.selection?.[0]?.team || null;
    // 2) Construire index id org -> entrée YAML
    this.orgIdIndex.clear();
    const teams = Array.isArray(this.yamlData?.teams) ? this.yamlData.teams : [];
    for (const t of teams) {
      const orgId = Number(t.api_football_org_team_id);
      if (!Number.isNaN(orgId) && orgId > 0) this.orgIdIndex.set(orgId, t);
    }
    // 3) Charger calendrier de l'équipe sélectionnée
    const safeShort = encodeURIComponent(String(this.selectedTeam || '').trim());
    const scheduleUrl = `/static/schedules/${safeShort}_schedule.json`;
    const rs = await fetch(scheduleUrl);
    if (!rs.ok) throw new Error('schedule load failed');
    const sj = await rs.json();
    this.scheduleMatches = Array.isArray(sj.matches) ? sj.matches : [];
    // 4) Trouver prochain match
    this.nextMatch = this.findNextMatchFromSchedule(this.scheduleMatches);
  }

  findNextMatchFromSchedule(matches) {
    const now = new Date();
    if (!Array.isArray(matches)) return null;
    // Priorité: match en cours/pausé
    const live = matches.find(m => m.status === 'IN_PLAY' || m.status === 'PAUSED');
    if (live) return live;
    // Sinon prochain match par date future
    const upcoming = matches
      .filter(m => {
        const d = new Date(m.utcDate || m.date);
        return !Number.isNaN(d.getTime()) && d > now;
      })
      .sort((a,b) => new Date(a.utcDate || a.date) - new Date(b.utcDate || b.date));
    return upcoming[0] || null;
  }

  normalizeMatchForPreset(m) {
    if (!m) return null;
    const d = new Date(m.utcDate || m.date);
    const yyyyMmDd = d.toISOString().slice(0,10);
    
    // Si eventLocation est fourni en attribut, l'utiliser
    let stade = this.eventLocation || '';
    let coords = null;
    
    // Sinon, déterminer l'équipe à domicile (homeTeam) et son entrée YAML
    if (!stade) {
      const homeId = Number(m.homeTeam?.id);
      const homeCfg = this.orgIdIndex.get(homeId) || null;
      stade = homeCfg?.stade || '';
      const latlng = homeCfg?.stade_lat_long || '';
      if (latlng && typeof latlng === 'string') {
        const parts = latlng.split(',').map(s => parseFloat(s.trim())).filter(v => !Number.isNaN(v));
        if (parts.length === 2) coords = [parts[1], parts[0]]; // [lon, lat]
      }
    }
    
    // Heure locale HH:MM, variante -2h (arrivée) et +2h (retour min)
    const hhmm = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    const minus2 = new Date(d.getTime() - 2 * 3600 * 1000);
    const plus2 = new Date(d.getTime() + 2 * 3600 * 1000);
    const hhmmMinus2 = minus2.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    const hhmmPlus2 = plus2.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    const endDate = plus2.toISOString().slice(0,10); // Date de fin (événement + 2h)
    return { date: yyyyMmDd, endDate, stadium: stade, coords, time: hhmm, timeMinus2: hhmmMinus2, timePlus2: hhmmPlus2 };
  }

  async presetFromNextMatch() {
    await this.loadYamlAndSchedule();
    const info = this.normalizeMatchForPreset(this.nextMatch);
    if (!info) return;
    // Mémorise les bornes liées au match pour validations
    this.matchDateStr = info.date;
    this.matchStartHHMM = info.time;
    this.matchMinReturnHHMM = info.timePlus2;
    // 1) Pré-régler la date
    const dateEl = this.shadowRoot.getElementById('date');
    if (dateEl && info.date) dateEl.value = info.date;
    const dateFindEl = this.shadowRoot.getElementById('date-find');
    // Ne pas pré-remplir date-find, laisser l'utilisateur choisir (switch désactivé par défaut)
    // if (dateFindEl && info.date) dateFindEl.value = info.date;
    const retDateOfferEl = this.shadowRoot.getElementById('return-date-offer');
    if (retDateOfferEl) {
      // borne min = date du match
      retDateOfferEl.min = info.date;
      if (!retDateOfferEl.value) retDateOfferEl.value = info.date;
    }
    // Ne pas pré-remplir return-date-find, laisser l'utilisateur choisir (switch désactivé par défaut)
    // const retDateFindEl = this.shadowRoot.getElementById('return-date-find');
    // if (retDateFindEl && info.endDate) {
    //   retDateFindEl.type = 'date'; // forcer le type date
    //   retDateFindEl.value = info.endDate;
    // }
    // 2) Pré-régler l'heure d'arrivée = heure du match - 2h si l'option existe
    const fromTimeSel = this.shadowRoot.getElementById('from-time');
    if (fromTimeSel && (info.timeMinus2 || info.time)) {
      const options = Array.from(fromTimeSel.options);
      // priorité à -2h
      if (info.timeMinus2) {
        const opt2 = options.find(o => o.value === info.timeMinus2);
        if (opt2) fromTimeSel.value = info.timeMinus2;
        else {
          const opt = options.find(o => o.value === info.time);
          if (opt) fromTimeSel.value = info.time;
        }
      } else if (info.time) {
        const opt = options.find(o => o.value === info.time);
        if (opt) fromTimeSel.value = info.time;
      }
    }
    // 2bis) Pré-régler l'heure de retour par défaut = heure du match + 2h (si disponible), sinon première option >= +2h
    const retTimeSel = this.shadowRoot.getElementById('return-time');
    if (retTimeSel && info.timePlus2) {
      // Désactive les options en-deçà du minimum si la date retour == date match
      this.updateReturnTimeOptionsDisabled(retTimeSel, (retDateOfferEl && retDateOfferEl.value) ? retDateOfferEl.value : info.date);
      const options = Array.from(retTimeSel.options);
      let chosen = options.find(o => o.value === info.timePlus2);
      if (!chosen) {
        // prend la première option >= timePlus2
        chosen = options.find(o => this.compareHHMM(o.value, info.timePlus2) >= 0);
      }
      if (chosen) retTimeSel.value = chosen.value;
    }
    // 3) Destination = stade de l'équipe à domicile
    const toInput = this.shadowRoot.getElementById('to');
    if (toInput && info.stadium) toInput.value = info.stadium;
    // 4) Position géographique = coords du stade -> place un marqueur d'arrivée
    if (info.coords) {
      // Mémoriser définitivement les coords du stade (centre du rayon)
      this.stadiumCoords = info.coords;
      // Si aucune destination n'a encore été posée, aligne la destination initiale sur le stade
      if (!this.endCoords) this.endCoords = info.coords;
      // remplace le marqueur existant
      if (this.endMarker) { try { this.endMarker.remove(); } catch(_){} }
      this.endMarker = new maplibregl.Marker({ color: 'green' }).setLngLat(this.endCoords).addTo(this.map);
      // cercle de 5 km autour de la destination pour visualiser la zone de stationnement
      this.updateDestinationRadius(3000);
      // Ajuster la vue pour inclure au moins le point d'arrivée (et départ si déjà connu)
      this.fitMapToBounds();
      // Vérifie proximité (devrait être à l'intérieur au preset)
      this.checkDestinationProximity(5000);
    }
    // Applique les contraintes de minimum retour à l'UI
    this.enforceReturnConstraints();
  }

  presetFromEventAttributes() {
    // Pré-remplir les champs depuis les attributs event-* passés au widget
    console.log('🔧 presetFromEventAttributes appelée', {
      eventDate: this.eventDate,
      eventLocation: this.eventLocation,
      eventTime: this.eventTime
    });
    
    // 1) Date
    if (this.eventDate) {
      const dateEl = this.shadowRoot.getElementById('date');
      console.log('📅 Champ date trouvé:', dateEl, 'value avant:', dateEl?.value);
      if (dateEl) {
        dateEl.value = this.eventDate;
        console.log('📅 Date définie à:', dateEl.value);
      }
    }
    
    // 2) Destination (eventLocation)
    if (this.eventLocation) {
      const toInput = this.shadowRoot.getElementById('to');
      console.log('📍 Champ destination trouvé:', toInput, 'value avant:', toInput?.value);
      if (toInput) {
        toInput.value = this.eventLocation;
        console.log('📍 Destination définie à:', toInput.value);
        // Déclencher une recherche de géocodage pour obtenir les coordonnées
        this.geocodeAddress(this.eventLocation).then(coords => {
          if (coords) {
            this.endCoords = coords;
            if (this.endMarker) { try { this.endMarker.remove(); } catch(_){} }
            this.endMarker = new maplibregl.Marker({ color: 'green' }).setLngLat(coords).addTo(this.map);
            this.fitMapToBounds();
          }
        }).catch(err => console.warn('Geocoding eventLocation failed:', err));
      }
    }
    
    // 3) Heure (eventTime) - si fournie
    if (this.eventTime) {
      const fromTimeSel = this.shadowRoot.getElementById('from-time');
      console.log('⏰ Champ heure trouvé:', fromTimeSel, 'value avant:', fromTimeSel?.value);
      if (fromTimeSel) {
        fromTimeSel.value = this.eventTime;
        console.log('⏰ Heure définie à:', fromTimeSel.value);
      }
    }
  }

  // Compare deux chaînes HH:MM; renvoie négatif si a<b, 0 si égal, positif si a>b
  compareHHMM(a, b) {
    if (!a || !b) return 0;
    return a.localeCompare(b);
  }

  // Désactive les options d'heure de retour < min quand la date correspond à celle du match; sinon réactive tout
  updateReturnTimeOptionsDisabled(retTimeSel, selectedDateStr) {
    if (!retTimeSel) return;
    const matchDate = this.matchDateStr;
    const minHHMM = this.matchMinReturnHHMM;
    const sameDay = matchDate && selectedDateStr === matchDate;
    Array.from(retTimeSel.options).forEach(opt => {
      if (sameDay && minHHMM) {
        opt.disabled = this.compareHHMM(opt.value, minHHMM) < 0;
      } else {
        opt.disabled = false;
      }
    });
    // Si la valeur actuelle est désormais invalide, bascule vers la première valide
    if (sameDay && minHHMM && this.compareHHMM(retTimeSel.value, minHHMM) < 0) {
      const firstValid = Array.from(retTimeSel.options).find(o => !o.disabled);
      if (firstValid) retTimeSel.value = firstValid.value;
    }
  }

  // Applique les règles: date retour >= date match; si même date, heure retour >= match+2h
  enforceReturnConstraints() {
    const retDateOfferEl = this.shadowRoot && this.shadowRoot.getElementById('return-date-offer');
    const retTimeSel = this.shadowRoot && this.shadowRoot.getElementById('return-time');
    if (!retDateOfferEl || !retTimeSel || !this.matchDateStr) return;
    // borne minimale date
    retDateOfferEl.min = this.matchDateStr;
    if (retDateOfferEl.value && retDateOfferEl.value < this.matchDateStr) {
      retDateOfferEl.value = this.matchDateStr;
    }
    // borne d'heures
    const effectiveDate = retDateOfferEl.value || this.matchDateStr;
    this.updateReturnTimeOptionsDisabled(retTimeSel, effectiveDate);
    // si aucune heure sélectionnée, choisir la première valide en fonction de la date
    if (!retTimeSel.value) {
      if (effectiveDate === this.matchDateStr && this.matchMinReturnHHMM) {
        const firstValid = Array.from(retTimeSel.options).find(o => !o.disabled);
        if (firstValid) retTimeSel.value = firstValid.value;
      } else {
        // valeur par défaut: première option (00:00)
        const first = retTimeSel.options[0];
        if (first) retTimeSel.value = first.value;
      }
    }
  }

  generateTimeOptions() {
    const times = [];
    for (let h = 0; h <= 23; h++) {
        times.push(`${h.toString().padStart(2, '0')}:00`);
        times.push(`${h.toString().padStart(2, '0')}:15`);
        times.push(`${h.toString().padStart(2, '0')}:30`);
        times.push(`${h.toString().padStart(2, '0')}:45`);
    }
    return times.map(t => `<option value="${t}">${t}</option>`).join("");
    }

  generateTimeValues() {
    const times = [];
    for (let h = 0; h <= 23; h++) {
      times.push(`${h.toString().padStart(2, '0')}:00`);
      times.push(`${h.toString().padStart(2, '0')}:15`);
      times.push(`${h.toString().padStart(2, '0')}:30`);
      times.push(`${h.toString().padStart(2, '0')}:45`);
    }
    return times;
  }


  async injectMapLibreResources() {
    if (!window.maplibregl) {
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://unpkg.com/maplibre-gl@2.4.0/dist/maplibre-gl.js";
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }
    
    // Charger JSTS pour des buffers rapides et propres (plus rapide que Turf)
    if (!window.jsts) {
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://unpkg.com/jsts@2.11.0/dist/jsts.min.js";
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }
  }

  renderError(title, message) {
    /**
     * Affiche un message d'erreur dans le widget (utilisé pour les erreurs de validation du code entreprise)
     */
    const isDark = this.theme === 'dark';
    const bgPrimary = isDark ? '#1e1e1e' : 'white';
    const textPrimary = isDark ? '#ffffff' : '#1e293b';
    const textSecondary = isDark ? '#9ca3af' : '#64748b';
    
    this.shadowRoot.innerHTML = `
      <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :host { display: block; width: 100%; font-family: ${this.fontFamily}; }
        .error-container {
          background: ${bgPrimary};
          border-radius: 16px;
          padding: 48px 32px;
          text-align: center;
          max-width: 600px;
          margin: 0 auto;
        }
        .error-icon {
          font-size: 64px;
          margin-bottom: 24px;
        }
        .error-title {
          font-size: 24px;
          font-weight: 800;
          color: ${textPrimary};
          margin-bottom: 16px;
        }
        .error-message {
          font-size: 16px;
          color: ${textSecondary};
          line-height: 1.6;
        }
        .error-message a {
          color: #667eea;
          text-decoration: underline;
        }
      </style>
      <div class="error-container">
        <div class="error-icon">⚠️</div>
        <div class="error-title">${title}</div>
        <div class="error-message">${message}</div>
      </div>
    `;
  }

  renderUI() {
    // Génération automatique des variantes de couleurs
    const generateColorVariants = (hexColor) => {
      // Convertir hex en RGB
      const hex = hexColor.replace('#', '');
      const r = parseInt(hex.substr(0, 2), 16);
      const g = parseInt(hex.substr(2, 2), 16);
      const b = parseInt(hex.substr(4, 2), 16);
      
      // Versions claires (mélange avec blanc)
      const light = `rgb(${Math.round(r + (255 - r) * 0.9)}, ${Math.round(g + (255 - g) * 0.9)}, ${Math.round(b + (255 - b) * 0.9)})`;
      const lighter = `rgb(${Math.round(r + (255 - r) * 0.8)}, ${Math.round(g + (255 - g) * 0.8)}, ${Math.round(b + (255 - b) * 0.8)})`;
      
      // Version foncée (réduction de 60% de la luminosité)
      const dark = `rgb(${Math.round(r * 0.4)}, ${Math.round(g * 0.4)}, ${Math.round(b * 0.4)})`;
      
      // Version pour gradient (légèrement plus foncée que la base)
      const gradient = `rgb(${Math.round(r * 0.85)}, ${Math.round(g * 0.85)}, ${Math.round(b * 0.85)})`;
      
      return { light, lighter, dark, gradient };
    };
    
    const outboundVariants = generateColorVariants(this.colorOutbound);
    const returnVariants = generateColorVariants(this.colorReturn);
    
    // Couleurs du thème jour/nuit
    const isDark = this.theme === 'dark';
    const bgPrimary = isDark ? '#000000' : '#ffffff';
    const bgSecondary = isDark ? '#1a1a1a' : '#f8f9fa';
    const bgTertiary = isDark ? '#2a2a2a' : '#f5f5f7';
    const textPrimary = isDark ? '#ffffff' : '#1D1D1F';
    const textSecondary = isDark ? '#a0a0a0' : '#6B6B6F';
    const textTertiary = isDark ? '#808080' : '#8E8E93';
    const borderColor = isDark ? '#3a3a3a' : '#e5e7eb';
    const borderLight = isDark ? '#2a2a2a' : '#f0f0f0';
    const cardBg = isDark ? '#1a1a1a' : '#ffffff';
    const cardBorder = isDark ? '#2a2a2a' : 'rgba(0,0,0,0.08)';
    const shadowColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)';
    const inputBg = isDark ? '#2a2a2a' : '#ffffff';
    const inputBorder = isDark ? '#3a3a3a' : '#D1D1D6';
    const hoverBg = isDark ? '#2a2a2a' : '#f6f7f8';
    
  this.shadowRoot.innerHTML = `
    <style>
      @import url("https://unpkg.com/maplibre-gl@2.4.0/dist/maplibre-gl.css");

      :host {
        display: flex;
        flex-direction: column;
        height: auto !important;
        max-width: 700px;
        margin: 24px auto;
        padding: 24px;
        background-color: ${bgPrimary};
        border-radius: 16px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
        font-family: ${this.fontFamily};
        color: ${textPrimary};
        box-sizing: border-box;
        /* Variables CSS pour les couleurs thématiques */
        --color-outbound: ${this.colorOutbound};
        --color-return: ${this.colorReturn};
        --color-outbound-light: ${outboundVariants.light};
        --color-outbound-lighter: ${outboundVariants.lighter};
        --color-outbound-dark: ${outboundVariants.dark};
        --color-outbound-gradient: ${outboundVariants.gradient};
        --color-return-light: ${returnVariants.light};
        --color-return-lighter: ${returnVariants.lighter};
        --color-return-dark: ${returnVariants.dark};
        --color-return-gradient: ${returnVariants.gradient};
      }

      /* iOS Segmented Control style tabs */
      .tabs {
        display: flex;
        gap: 4px;
        background: rgba(118, 118, 128, 0.12);
        padding: 2px;
        border-radius: 10px;
        margin: 12px 16px 16px 16px;
        position: relative;
        width: calc(100% - 32px);
      }
      .tab {
        background: transparent;
        border: none;
        padding: 8px 12px;
        color: ${textPrimary};
        font-weight: 400;
        font-size: 15px;
        line-height: 1.3;
        flex: 1 1 33.33%;
        text-align: center;
        border-radius: 8px;
        transition: all 0.25s cubic-bezier(0.4, 0.0, 0.2, 1);
        font-family: ${this.fontFamily};
        -webkit-font-smoothing: antialiased;
        position: relative;
        z-index: 1;
      }
      .tab.active {
        background: ${cardBg};
        color: ${textPrimary};
        font-weight: 600;
        box-shadow: 0 1px 3px ${shadowColor}, 0 1px 2px ${shadowColor};
      }
      @media (hover: hover) {
        .tab:not(.active):hover { 
          color: ${textSecondary};
        }
      }


      .form {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-bottom: 20px;
        padding: 12px 12px 12px 12px; /* top & bottom uniquement */
        }

    .form select {
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #ccc;
        font-size: 16px;
        font-family: ${this.fontFamily};
        }


      .form input[type="text"],
      .form input[type="datetime-local"],
      .form button {
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #ccc;
        font-size: 16px;
        width: 100%;
        color: ${textPrimary};
      }

      .form input[type="checkbox"] {
        margin-right: 8px;
      }

      /* Styles pour le slider de détour RSE */
      #rse-max-detour-time::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: ${this.colorOutbound};
        cursor: pointer;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
      }

      #rse-max-detour-time::-moz-range-thumb {
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: ${this.colorOutbound};
        cursor: pointer;
        border: none;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
      }

      .form label {
        font-size: 15px;
        display: flex;
        align-items: center;
        gap: 6px;
        color: #555;
      }

      .form button {
        background-color: #02a702b6;
        color: white;
        font-weight: bold;
        cursor: pointer;
        transition: background 0.2s ease-in-out;
      }

      .form button:hover {
        background-color: #42943aff;
      }

      .map {
        width: 70% !important;
        max-width: 500px;
        margin: 0 auto;
        display: block;
        height: 400px !important;
        min-height: 400px !important;
        border: 1px solid #ddd;
        border-radius: 12px;
        overflow: hidden !important;
      }
      /* Sur mobile, réduire la hauteur de la map pour voir les cartes en dessous */
      @media (max-width: 768px) {
        .map {
          height: 280px !important;
          min-height: 280px !important;
        }
      }
      .legend {
        width: 80%;
        max-width: 500px;
        margin: 12px auto 0 auto;
        display: none; /* Masquer la légende sur pages 2 et 3 */
        gap: 24px;
        font-size: 15px;
        color: #555;
        align-items: center;
      }
      .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .legend-line {
        width: 32px;
        height: 0;
        border-top: 4px solid var(--color-outbound);
      }
      .legend-line-return {
        width: 32px;
        height: 0;
        border-top: 4px dashed var(--color-return);
      }
      /* Sélection / actions offres */
      .offer-card { transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
      .offer-card:not(.selected):hover { 
        box-shadow: 0 8px 28px rgba(0,0,0,0.16);
        transform: translateY(-2px);
      }
      .offer-card.selected { border-color: var(--brand); box-shadow:0 6px 24px rgba(30,143,46,0.2); }
      .offer-card .actions { display:flex; align-items:center; gap:8px; margin-top:4px; }
      .offer-card .actions.actions-vertical { display:flex; flex-direction:column; align-items:flex-start; gap:6px; }
  .offer-card button.btn-reserve { background: var(--brand); color:#fff; border:1px solid var(--brand); padding:8px 16px; font-size:16px; border-radius:10px; cursor:pointer; }
  .offer-card .header-row { display:flex; align-items:center; gap:12px; }
  .avatar-circle { width:48px; height:48px; border-radius:50%; flex:0 0 48px; overflow:hidden; background:#e0e0e0; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:18px; color:#555; box-shadow:0 2px 6px rgba(0,0,0,0.12); }
  .avatar-circle img { width:100%; height:100%; object-fit:cover; display:block; }
      .offer-card button.btn-reserve:hover { background: var(--brand-strong); border-color: var(--brand-strong); }
    /* Danger button (Annuler) */
    .offer-card button.btn-danger { background:#dc2626; color:#fff; border:1px solid #dc2626; padding:8px 16px; font-size:16px; border-radius:10px; cursor:pointer; box-shadow:0 2px 6px rgba(220,38,38,0.35); }
    .offer-card button.btn-danger:hover { background:#b91c1c; border-color:#b91c1c; }
  /* Confirm button - light (blanchi) style */
  .offer-card button.btn-confirm { background:#eff6ff; color:#1d4ed8; border:1px solid #93c5fd; padding:6px 10px; font-size:13px; border-radius:8px; cursor:pointer; }
  .offer-card button.btn-confirm:hover { background:#dbeafe; border-color:#60a5fa; }
  /* Passengers strip */
  .passengers { border-top:1px dashed #eee; margin-top:6px; padding-top:6px; padding-left:8px; display:flex; flex-direction:column; gap:6px; }
  .passenger { display:flex; align-items:center; gap:8px; font-size:13px; color:#333; padding-left:8px; }
  .passenger + .passenger { border-top: 1px solid #eee; padding-top: 6px; }
    .avatar-sm { width:28px; height:28px; border-radius:50%; object-fit:cover; box-shadow:0 1px 3px rgba(0,0,0,0.12); }
    .avatar-md { width:40px; height:40px; border-radius:50%; object-fit:cover; box-shadow:0 1px 3px rgba(0,0,0,0.12); }
  .status-badge { display:inline-block; padding:3px 8px; border-radius:999px; font-size:12px; font-weight:700; }
  .status-confirmed { background:#dcfce7; color:#166534; border:1px solid #86efac; font-size:13px; font-weight:800; padding:4px 10px; }
    .status-pending { background:#fff7ed; color:#9a3412; border:1px solid #fed7aa; }
  .pax-actions { display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
  /* Pending button acts as confirm trigger */
  .offer-card button.btn-pending { background:#fff7ed; color:#9a3412; border:1px solid #fed7aa; padding:6px 12px; font-size:13px; border-radius:999px; cursor:pointer; }
  .offer-card button.btn-pending:hover { background:#ffedd5; border-color:#fdba74; }
  /* Reject button - same look as confirm, but red tinted */
  .offer-card button.btn-reject { background:#fef2f2; color:#b91c1c; border:1px solid #fecaca; padding:6px 12px; font-size:13px; border-radius:999px; cursor:pointer; }
  .offer-card button.btn-reject:hover { background:#fee2e2; border-color:#fca5a5; }
      .modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center; z-index:16000; }
      .modal { background:#fff; width:90%; max-width:420px; border-radius:14px; padding:20px 22px; box-shadow:0 8px 28px rgba(0,0,0,0.25); font-family:${this.fontFamily}; }
      .modal h2 { margin:0 0 12px 0; font-size:20px; font-weight:700; }
      .modal p { font-size:14px; line-height:1.4; color:#333; margin:0 0 12px 0; }
      .modal .warning { background:#fff8e1; border:1px solid #ffecb3; padding:10px 12px; border-radius:8px; font-size:13px; color:#8d6e00; margin-bottom:14px; }
      .modal .buttons { display:flex; justify-content:flex-end; gap:10px; margin-top:6px; }
      .modal button { border:1px solid #ccc; background:#f5f5f5; padding:8px 14px; font-size:14px; border-radius:8px; cursor:pointer; }
      .modal button.confirm { background: var(--brand); color:#fff; border-color: var(--brand); font-weight:600; }
      .modal button.confirm:hover { background: var(--brand-strong); }
        .datetime-group {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        }

  /* Offre uniquement (caché côté "Trouver") */
  .offer-only { display: none !important; }
  /* Affichage affiné: ne pas casser le layout flex des meta-items */
  .meta-item.offer-only.visible { display: flex !important; }
  /* Section des étapes: bloc standard */
  #stops-section.offer-only.visible { display: block !important; }
  /* Search fields dans la carte */
  .search-card .search-field.offer-only.visible { display: flex !important; }
  /* Éléments inline dans search-field (divider, icon, select) */
  .search-field .offer-only { display: none !important; }
  .search-field .offer-only.visible { display: inline-flex !important; }
  /* Fallback générique si autre conteneur */
  .offer-only.visible:not(.meta-item):not(#stops-section):not(.search-field) { display: block !important; }

  /* Find uniquement (caché côté "Proposer" et "Mes trajets") */
  .find-only[hidden] { display: none !important; }
  .search-field .find-only[hidden] { display: none !important; }
  .search-field .find-only:not([hidden]) { display: inline-flex !important; }
  .find-only.label-text:not([hidden]) { display: inline !important; }
        
        /* iOS-style stops */
        .stops {
          display: flex;
          flex-direction: column;
          gap: 0;
          margin: 0;
        }
        .stop-row {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 14px 16px;
          border-bottom: 0.5px solid rgba(0,0,0,0.08);
          transition: background 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
          position: relative;
          min-height: 52px;
          background: transparent;
        }
        .stop-row:last-child { border-bottom: none; }
        .stop-row:active { 
          background: rgba(0,0,0,0.04);
          transition: background 0.05s;
        }
        @media (hover: hover) {
          .stop-row:hover { 
            background: rgba(0,0,0,0.02);
          }
        }
        .stop-bullet {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #8e8e93;
          flex-shrink: 0;
        }
        .stop-row input[type="text"],
        .stop-row input {
          border: none;
          background: transparent;
          height: auto;
          padding: 0;
          font-size: 17px;
          color: ${textPrimary};
          outline: none;
          flex: 1;
          font-family: ${this.fontFamily};
          -webkit-font-smoothing: antialiased;
          font-weight: 400;
        }
        .stop-row input::placeholder {
          color: ${isDark ? '#636366' : '#c7c7cc'};
        }
        /* Champ d'ajout d'étape - style plus subtil */
        .stop-row.add-stop-field {
          background: transparent;
        }
        .stop-row.add-stop-field .stop-bullet {
          background: #d1d1d6;
        }
        .stop-row.add-stop-field input::placeholder {
          color: #a0a0a8;
          font-weight: 400;
        }
        /* iOS-style remove button (minimalist) */
        .stop-row .btn-remove-stop {
          flex-shrink: 0;
          width: 28px;
          height: 28px;
          padding: 0;
          border-radius: 50%;
          border: none;
          background: rgba(255,59,48,0.1);
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          -webkit-appearance: none;
          appearance: none;
          -webkit-tap-highlight-color: transparent;
        }
        .stop-row .btn-remove-stop .icon-minus {
          display: block;
          width: 12px;
          height: 2px;
          background: #ff3b30;
          border-radius: 1px;
        }
        .stop-row .btn-remove-stop:active { 
          background: rgba(255,59,48,0.2);
          transform: scale(0.95);
        }
        @media (hover: hover) {
          .stop-row .btn-remove-stop:hover { 
            background: rgba(255,59,48,0.15);
          }
        }

        /* Time selects inline */
        /* Style commun pour les sélecteurs d'heure */
        .time-select {
          border: none;
          background: transparent;
          height: auto;
          padding: 0;
          font-size: 17px;
          color: #8e8e93;
          font-family: ${this.fontFamily};
          -webkit-font-smoothing: antialiased;
          outline: none;
        }
        .stop-time {
          border: none;
          background: transparent;
          height: auto;
          padding: 0;
          font-size: 15px;
          color: #8e8e93;
          font-family: ${this.fontFamily};
          -webkit-font-smoothing: antialiased;
          outline: none;
          flex-shrink: 0;
        }

        /* Route stack (ligne pointillée verticale derrière les encarts) */
        .route-stack { position: relative; padding-left: 28px; margin: 6px 0 10px 0; }
        .route-stack::before {
          content: "";
          position: absolute;
          left: 14px;
          top: 53px; /* commence juste sous le point bleu (top 47 + rayon 6) */
          bottom: 26px; /* s'arrête au centre du capuchon vert (bottom 20 + rayon 6) */
          border-left: 2px dashed #cbd5e1; /* gris clair */
          z-index: 0;
        }
        .route-stack .with-icon,
        .route-stack .stop-row { position: relative; z-index: 1; }
  .route-cap { position:absolute; width:12px; height:12px; border-radius:50%; z-index:0; }
  /* Top cap: blue and vertically centered with first input card */
  .route-cap-top { left:8px; top:47px; background: var(--color-outbound); box-shadow: 0 1px 3px rgba(0,0,0,0.15); }
  /* Bottom cap: green (brand) instead of grey */
  .route-cap-bottom { left:8px; bottom:20px; background: var(--brand); box-shadow: 0 1px 3px rgba(0,0,0,0.15); }

  /* Overlay de chargement carte */
  .map-box { position: relative; }
  .map-loading { position: absolute; inset: 0; background: ${isDark ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,255,0.6)'}; display: flex; align-items: center; justify-content: center; z-index: 5; backdrop-filter: saturate(120%) blur(1px); }
  .map-loading[hidden] { display: none !important; }
  
  /* Cacher la carte et la légende dans l'onglet "Trouver un covoit" */
  :host([data-active-tab="find"]) #map-box-container,
  :host([data-active-tab="find"]) #map-legend {
    display: none !important;
  }
  
  .meta-row { display: grid; grid-template-columns: repeat(auto-fit,minmax(140px,1fr)); gap: 12px; margin-top: 8px; }
  .meta-row .meta-item { display:flex; flex-direction:column; gap:6px; }
  .meta-row .meta-item label { font-size:13px; font-weight:600; color: var(--ink-2); }
        .meta-row select, .meta-row input[type="date"] {
          height:40px;
          min-height:40px;
          padding:8px 12px;
          border:1px solid var(--border);
          border-radius:10px;
          background:${cardBg};
          color:${textPrimary};
          font-size:14px;
          line-height:22px;
          box-sizing:border-box;
        }
  /* Prix suggéré */
  .price-hint { font-size: 12px; color: var(--ink-3); margin-top: 2px; }
  .checkbox-inline { display:flex; align-items:center; gap:8px; font-size:13px; color: var(--ink-2); }
  #price-per-passenger { height: 40px; min-height: 40px; padding:8px 12px; border:1px solid var(--border); border-radius:10px; font-size:14px; }
  /* Liste des tarifs par point de montée */
  .price-list { list-style: none; padding-left: 0; margin: 6px 0 0 0; }
  .price-list li { font-size: 13px; color: var(--ink-2); display:flex; justify-content: space-between; align-items:center; gap:12px; padding: 6px 0; border-bottom: 1px dashed #eee; }
  .price-list li:last-child { border-bottom: none; }
  .price-list .right { 
    display: flex; 
    flex-direction: column;
    align-items: flex-end; 
    gap: 4px; 
  }
  .price-list .right > div:first-child {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .segment-price { 
    width: 80px; 
    text-align: right; 
    height: 38px; 
    border: 2px solid #34c759; 
    border-radius: 10px; 
    padding: 4px 8px; 
    font-size: 18px;
    font-weight: 700;
    color: #34c759;
    background: rgba(52, 199, 89, 0.08);
    transition: all 0.2s ease;
  }
  .segment-price:focus {
    outline: none;
    border-color: #30d158;
    background: rgba(52, 199, 89, 0.12);
    box-shadow: 0 0 0 3px rgba(52, 199, 89, 0.15);
  }
  .suggested-price {
    display: block;
    font-size: 11px;
    color: #34c759;
    font-weight: 600;
    margin-top: 4px;
    text-align: right;
  }
  .dist { color: var(--ink-3); font-size: 12px; }
  /* Titres et entêtes de colonnes des tarifs */
  .prices-subtitle { font-size: 15px; font-weight: 700; color: #222; margin-top: 8px; margin-bottom: 4px; }
  .prices-header { display:flex; justify-content: space-between; align-items:center; font-size: 12px; color: var(--ink-3); margin: 0 0 2px 0; }
  .prices-header .col-right { width: 90px; text-align: right; }
        /* Forcer les dates en noir et gras, y compris sur iOS */
        .meta-row input[type="date"],
        .datetime-group .date-block input[type="date"] {
          color:#111;
          font-weight:700;
          -webkit-text-fill-color:#111; /* iOS/WebKit */
        }
        /* iOS/WebKit sous-parties du champ date */
        .meta-row input[type="date"]::-webkit-datetime-edit,
        .meta-row input[type="date"]::-webkit-datetime-edit-text,
        .meta-row input[type="date"]::-webkit-datetime-edit-month-field,
        .meta-row input[type="date"]::-webkit-datetime-edit-day-field,
        .meta-row input[type="date"]::-webkit-datetime-edit-year-field,
        .datetime-group .date-block input[type="date"]::-webkit-datetime-edit,
        .datetime-group .date-block input[type="date"]::-webkit-datetime-edit-text,
        .datetime-group .date-block input[type="date"]::-webkit-datetime-edit-month-field,
        .datetime-group .date-block input[type="date"]::-webkit-datetime-edit-day-field,
        .datetime-group .date-block input[type="date"]::-webkit-datetime-edit-year-field {
          color:#111;
          font-weight:700;
        }
        .meta-row input[type="date"] {
          -webkit-appearance:none;
          appearance:none;
        }
  .spinner { width: 38px; height: 38px; border: 3px solid #e5e7eb; border-top-color: var(--brand); border-radius: 50%; animation: spin .8s linear infinite; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  @keyframes spin { to { transform: rotate(360deg); } }

        .date-block,
        .time-block {
        flex: 1;
        max-width: 200px;
        display: flex;
        flex-direction: column;
        }

        .date-block label,
        .time-block label {
        font-size: 14px;
        color: #555;
        margin-bottom: 4px;
        font-weight: 500;
        }

        .date-block input,
        .time-block input {
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #ccc;
        font-size: 16px;
        height: 42px;
        font-family: ${this.fontFamily};
        }
        .form input[type="text"],
        .form input[type="date"],
        .form select {
        padding: 10px;
        height: 42px;
        border-radius: 8px;
        border: 1px solid #ccc;
        font-size: 16px;
        font-family: ${this.fontFamily};
        box-sizing: border-box;
        }

        .form input[type="text"] {
            /* forme */
          border-radius: 999px
          padding: 0 18px
          height: 48px

          /* bordures/typo */
          border: 1px solid #e0e0e0 !important;
          box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
          font-size: 17px
          color: #111

          /* couleur de fond – UTILISE background-color (pas shorthand) */
          background-color: #09097e !important;          /* hex “classique” */
          /* fallback/compat si jamais */
          /* background-color: rgba(9,9,126,1) !important; */

          /* neutralisation plateforme */
          -webkit-appearance: none;
          appearance: none;
        }

        /* Règle générale (sans !important si possible) */
        .form input[type="text"] {
            padding: 10px;
            height: 42px;
            border-radius: 8px;
            border: 1px solid #ccc;
            font-size: 16px;
            font-family: ${this.fontFamily};
            box-sizing: border-box;
        }

        /* Règles spécifiques pour #from et #to - sans background ni bordures visibles */
        #from, #to {
            border: none;
            padding: 0;
            height: auto;
            box-shadow: none;
            font-size: 17px;
            color: ${textPrimary};
            background: transparent;
            -webkit-appearance: none;
            appearance: none;
        }

        /* Mobile-only styles for detour route timeline */
        @media (max-width: 480px) {
            .detour-gradient {
                width: 40px !important;
            }
            .detour-info {
                padding: 0 6px !important;
            }
            .date-text {
                font-size: 10px !important;
            }
            .time-text {
                font-size: 18px !important;
            }
            .duration-text {
                font-size: 12px !important;
            }
            .detour-address {
                font-size: 11px !important;
                margin-top: 6px !important;
            }
            .address-row {
                font-size: 11px !important;
            }
        }

    </style>
  <style>
    /* --- UI polish overrides --- */
    :host { --brand: #1e8f2e; --brand-strong:#0a7a16; --border:#e5e7eb; --ink-2:#666; --ink-3:#999; }
    .card { 
      background: ${cardBg}; 
      border-radius: 20px; 
      box-shadow: 0 2px 8px ${shadowColor}, 0 8px 32px ${shadowColor}; 
      border: 0.5px solid ${cardBorder}; 
      overflow: hidden;
      position: relative;
    }
    .map { width:100% !important; max-width:none; margin:0; border-radius:14px; }
    /* Laisse un espace latéral (mobile) pour pouvoir scroller en dehors de la carte */
    @media (max-width: 768px) {
      /* Utiliser un padding sur le conteneur pour garantir une gouttière cliquable des deux côtés,
         même avec overflow hidden des parents et width:100% sur la carte. */
      .map-box { padding: 0 50px; }
      .map { margin: 0; width: 100% !important; }
    }
    .legend { width:100%; max-width:none; margin: 10px 0 0 0; padding: 0 12px 12px 12px; color: var(--ink-2); }
    .form label { font-size:14px; color: var(--ink-2); gap:8px; }
    
    /* iOS-style primary button */
    .btn-primary { 
      background: var(--brand); 
      color: #fff; 
      border: none; 
      font-weight: 600; 
      font-size: 17px;
      border-radius: 14px;
      padding: 14px 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 4px 12px rgba(30,143,46,0.2);
      transition: all 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
      font-family: ${this.fontFamily};
      -webkit-font-smoothing: antialiased;
      cursor: pointer;
    }
    .btn-primary:active { 
      background: var(--brand-strong); 
      transform: scale(0.98);
      box-shadow: 0 1px 2px rgba(0,0,0,0.1), 0 2px 8px rgba(30,143,46,0.15);
    }
    @media (hover: hover) {
      .btn-primary:hover { 
        background: var(--brand-strong); 
        box-shadow: 0 2px 4px rgba(0,0,0,0.14), 0 6px 16px rgba(30,143,46,0.25);
      }
    }

    /* Icon fields */
    .field { display:flex; flex-direction:column; gap:6px; }
    .with-icon { display:flex; align-items:center; gap:10px; border:1px solid var(--border); border-radius:999px; background:#fff; padding:6px 10px; box-shadow:0 1px 4px rgba(0,0,0,0.03); }
  /* Pour pouvoir positionner les suggestions juste sous le champ */
  .with-icon { position: relative; }
    .with-icon .icon { width:18px; height:18px; color: var(--ink-3); display:inline-flex; }
    .with-icon input[type="text"] { border:none; background:transparent; height:38px; padding:0 8px; flex:1; font-size:17px; color:#111; outline:none; }

    /* iOS Switch for return trip */
    .switch-ios { 
      position: relative; 
      display: inline-block; 
      width: 51px; 
      height: 31px; 
      flex-shrink: 0;
    }
    .switch-ios input { 
      opacity: 0; 
      width: 0; 
      height: 0; 
      position: absolute;
    }
    .switch-ios-slider { 
      position: absolute; 
      cursor: pointer; 
      inset: 0; 
      background: #e9e9ea;
      transition: background 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
      border-radius: 999px;
    }
    .switch-ios-slider:before { 
      content: ""; 
      position: absolute; 
      height: 27px; 
      width: 27px; 
      left: 2px; 
      bottom: 2px; 
      background: ${bgPrimary}; 
      transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
      border-radius: 50%; 
      box-shadow: 0 2px 4px ${shadowColor}, 0 1px 2px ${shadowColor};
    }
    input:checked + .switch-ios-slider { 
      background: #34c759;
    }
    input:checked + .switch-ios-slider:before { 
      transform: translateX(20px);
    }
    .switch-ios-slider:active:before {
      width: 32px;
    }
    
    /* Switch bleu pour l'aller */
    .switch-ios-blue input:checked + .switch-ios-slider {
      background: var(--color-outbound);
    }
    
    /* Switch orange pour le retour */
    .switch-ios-orange input:checked + .switch-ios-slider {
      background: var(--color-return);
    }

    /* Return options collapsible section */
    .return-options {
      overflow: hidden;
      max-height: 0;
      opacity: 0;
      transition: max-height 0.3s cubic-bezier(0.4, 0.0, 0.2, 1), opacity 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
    }
    .return-options.expanded {
      max-height: 500px;
      opacity: 1;
    }
    .return-options .search-field {
      border-top: 0.5px solid rgba(0,0,0,0.08);
    }

    /* Hide return toggle in "Find" tab */
    .find-only-active .return-toggle-field,
    .find-only-active .return-options {
      display: none !important;
    }

    /* Panneau de suggestions (mobile) */
    .suggestions {
      position: absolute;
      left: 0;
      right: 0;
      top: 100%;
      margin-top: 2px;
      background: ${cardBg};
      border: 1px solid ${cardBorder};
      border-radius: 10px;
      box-shadow: 0 8px 24px ${shadowColor};
      max-height: 260px;
      overflow: auto;
      z-index: 15000;
    }
    .suggestion-item { padding: 10px 12px; cursor: pointer; font-size: 15px; color:${textPrimary}; }
    .suggestion-item:hover { background: ${hoverBg}; }

    /* Bouton Calculer l'itinéraire - iOS style */
    .btn-calculate {
      width: 100%;
      padding: 16px 20px;
      background: linear-gradient(135deg, var(--color-outbound), var(--color-outbound-dark));
      color: #fff;
      border: none;
      border-radius: 14px;
      font-size: 17px;
      font-weight: 600;
      font-family: ${this.fontFamily};
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 14px rgba(0, 122, 255, 0.3);
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
    }
    .btn-calculate:hover {
      background: linear-gradient(135deg, #0051d5, #003d9e);
      box-shadow: 0 6px 20px rgba(0, 122, 255, 0.4);
      transform: translateY(-1px);
    }
    .btn-calculate:active {
      transform: translateY(0);
      box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3);
    }
    .btn-calculate:disabled {
      background: linear-gradient(135deg, #8e8e93, #636366);
      cursor: not-allowed;
      opacity: 0.6;
      transform: none;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    .btn-calculate:disabled:hover {
      background: linear-gradient(135deg, #8e8e93, #636366);
      transform: none;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    /* Cartes d'alternatives de trajet (étape 2) - disposition horizontale */
    #route-selection-wrapper {
      margin: 16px;
    }
    #route-alternatives-list {
      display: grid;
      grid-template-columns: repeat(3, 1fr) !important;
      gap: 16px;
    }
    /* Si 2 trajets : prendre toute la largeur */
    #route-alternatives-list:has(.route-alternative-card:nth-child(2):last-child) {
      grid-template-columns: repeat(2, 1fr) !important;
    }
    /* Si 1 seul trajet : prendre toute la largeur */
    #route-alternatives-list:has(.route-alternative-card:only-child) {
      grid-template-columns: 1fr !important;
    }
    /* Sur mobile : 3 cartes compactes côte à côte sans scroll */
    @media (max-width: 768px) {
      #route-selection-wrapper {
        margin: 12px 0 !important;
      }
      #route-alternatives-list {
        display: grid;
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 4px;
        padding: 0 4px;
      }
      /* Si 2 trajets mobile : 2 colonnes */
      #route-alternatives-list:has(.route-alternative-card:nth-child(2):last-child) {
        grid-template-columns: repeat(2, 1fr) !important;
      }
      /* Si une seule carte : prendre toute la largeur */
      #route-alternatives-list:has(.route-alternative-card:only-child) {
        grid-template-columns: 1fr !important;
      }
      .route-alternative-card {
        padding: 8px;
        gap: 6px;
        font-size: 13px;
        /* Forcer la largeur pour éviter l'élargissement */
        min-width: 0;
        width: 100%;
        overflow: hidden;
      }
      .route-alternative-card .route-title {
        font-size: 14px;
      }
      .route-alternative-card .route-badge {
        padding: 3px 7px;
        font-size: 11px;
        font-weight: 700;
      }
      .route-alternative-card .route-stats {
        flex-direction: column;
        align-items: flex-start;
        gap: 4px;
      }
      .route-alternative-card .stat-item {
        font-size: 12px;
      }
      .route-alternative-card .stat-icon {
        width: 14px;
        height: 14px;
      }
      /* Stats en colonne : label au-dessus, valeur centrée en dessous */
      .route-alternative-card .route-meta {
        gap: 10px;
      }
      .route-alternative-card .route-meta-item {
        flex-direction: column;
        align-items: center;
        text-align: center;
        gap: 4px;
        font-size: 12px;
      }
      .route-alternative-card .route-meta-item svg {
        width: 16px;
        height: 16px;
        margin-bottom: 2px;
      }
      .route-alternative-card .route-meta-item strong {
        font-size: 11px;
        font-weight: 600;
        color: ${textSecondary};
        min-width: auto;
      }
      .route-alternative-card .route-meta-item span {
        font-size: 13px;
        font-weight: 700;
        color: ${textPrimary};
      }
      /* Masquer l'itinéraire sur mobile pour gagner de la place */
      .route-alternative-card .route-via {
        display: none;
      }
      /* Ajuster la position de la checkmark sur mobile */
      .route-alternative-card .checkmark {
        top: 8px;
        right: 8px;
        width: 20px;
        height: 20px;
      }
      .route-alternative-card .btn-select-route {
        padding: 8px 12px;
        font-size: 13px;
        width: 100%;
        box-sizing: border-box;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }
    /* Suppression des media queries qui cassent la disposition */
    .route-alternative-card {
      background: ${isDark ? 'rgba(28, 28, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)'};
      backdrop-filter: saturate(180%) blur(20px);
      -webkit-backdrop-filter: saturate(180%) blur(20px);
      border-radius: 16px;
      border: 2px solid ${isDark ? '#3a3a3c' : '#d1d1d6'};
      padding: 16px;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
      position: relative;
      display: flex;
      flex-direction: column;
      gap: 12px;
      box-sizing: border-box;
    }
    .route-alternative-card:hover {
      border-color: var(--color-outbound);
      box-shadow: 0 4px 16px var(--color-outbound-lighter);
      transform: translateY(-2px);
    }
    .route-alternative-card.selected {
      border-color: var(--color-outbound);
      border-width: 3px;
      border-top-width: 32px;
      background: linear-gradient(135deg, var(--color-outbound-lighter), var(--color-outbound-lighter));
      box-shadow: 0 6px 20px var(--color-outbound-light);
      position: relative;
    }
    .route-alternative-card.selected::before {
      content: 'Votre aller';
      position: absolute;
      top: -28px;
      left: 8px;
      font-size: 14px;
      font-weight: 700;
      color: white;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    /* Routes retour - même apparence que l'aller mais avec couleur return */
    .route-alternative-card.return-route:hover {
      border-color: var(--color-return);
      box-shadow: 0 4px 16px var(--color-return-lighter);
    }
    .route-alternative-card.return-route.selected {
      border-color: var(--color-return);
      border-width: 3px;
      border-top-width: 32px;
      background: linear-gradient(135deg, var(--color-return-lighter), var(--color-return-lighter));
      box-shadow: 0 6px 20px var(--color-return-light);
      position: relative;
    }
    .route-alternative-card.return-route.selected::before {
      content: 'Votre retour';
      position: absolute;
      top: -28px;
      left: 8px;
      font-size: 14px;
      font-weight: 700;
      color: white;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .route-alternative-card.return-route.selected .route-badge {
      background: var(--color-return) !important;
    }
    .route-alternative-card.return-route.selected .checkmark {
      background: var(--color-return) !important;
      border-color: var(--color-return) !important;
    }
    .route-alternative-card.return-route.selected .btn-select-route {
      background: var(--color-return) !important;
      border-color: var(--color-return) !important;
    }
    .route-alternative-card .route-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .route-alternative-card .route-title {
      font-size: 17px;
      font-weight: 700;
      color: ${textPrimary};
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .route-alternative-card .route-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px 10px;
      background: #8e8e93;
      color: #fff;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 700;
    }
    .route-alternative-card.selected .route-badge {
      background: var(--color-outbound);
    }
    .route-alternative-card .route-meta {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .route-alternative-card .route-meta-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      color: ${textPrimary};
    }
    .route-alternative-card .route-meta-item svg {
      width: 18px;
      height: 18px;
      color: ${textSecondary};
      flex-shrink: 0;
    }
    .route-alternative-card .route-meta-item strong {
      font-weight: 600;
      min-width: 60px;
    }
    .route-alternative-card .route-via {
      font-size: 13px;
      color: ${textSecondary};
      margin-top: 4px;
      line-height: 1.4;
      padding-top: 8px;
      border-top: 1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)'};
    }
    .route-alternative-card .route-via strong {
      color: ${textPrimary};
      font-weight: 600;
      display: block;
      margin-bottom: 4px;
    }
    .route-alternative-card .checkmark {
      position: absolute;
      top: 16px;
      right: 16px;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: #34c759;
      display: none;
      align-items: center;
      justify-content: center;
    }
    .route-alternative-card.selected .checkmark {
      display: flex;
    }
    .route-alternative-card .btn-select-route {
      margin-top: 8px;
      width: 100%;
      padding: 10px;
      background: ${bgTertiary};
      color: ${textPrimary};
      border: 1px solid ${inputBorder};
      border-radius: 10px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .route-alternative-card:hover .btn-select-route {
      background: var(--color-outbound);
      color: ${bgPrimary};
      border-color: var(--color-outbound);
    }
    .route-alternative-card.return-route:hover .btn-select-route {
      background: var(--color-return);
      color: ${bgPrimary};
      border-color: var(--color-return);
    }
    .route-alternative-card.selected .btn-select-route {
      background: var(--color-outbound);
      color: #fff;
      border-color: var(--color-outbound);
    }
    .route-alternative-card.return-route.selected .btn-select-route {
      background: var(--color-return);
      color: #fff;
      border-color: var(--color-return);
    }
    /* Bouton annuler sur carte sélectionnée */
    .route-alternative-card .btn-select-route.btn-cancel {
      background: #ff3b30;
      color: #fff;
      border-color: #ff3b30;
    }
    .route-alternative-card .btn-select-route.btn-cancel:hover {
      background: #d32f2f;
      border-color: #d32f2f;
    }

    /* Encart récapitulatif - iOS style glassmorphism matching top card */
    .trip-summary {
      background: linear-gradient(135deg, ${cardBg} 0%, ${bgSecondary} 100%);
      backdrop-filter: saturate(180%) blur(20px);
      -webkit-backdrop-filter: saturate(180%) blur(20px);
      border-radius: 20px;
      box-shadow: 0 4px 16px ${shadowColor}, 0 12px 40px ${shadowColor};
      margin: 16px;
      overflow: hidden;
      border: 1px solid ${cardBorder};
      animation: slideIn 0.4s cubic-bezier(0.4, 0.0, 0.2, 1);
    }
    @keyframes slideIn {
      from { opacity: 0; transform: translateY(-15px) scale(0.98); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }

    .summary-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 20px 20px;
      background: linear-gradient(135deg, #28a745 0%, #34c759 100%);
      border-bottom: none;
      font-size: 18px;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: -0.3px;
    }
    .summary-header svg {
      flex-shrink: 0;
      color: rgba(255, 255, 255, 0.95);
      width: 24px;
      height: 24px;
      filter: drop-shadow(0 1px 2px rgba(0,0,0,0.15));
    }

    .summary-intro {
      padding: 20px;
      background: linear-gradient(135deg, rgba(40, 167, 69, 0.08) 0%, rgba(40, 167, 69, 0.02) 100%);
      border-bottom: 1px solid rgba(40, 167, 69, 0.15);
    }
    .summary-intro-title {
      font-size: 15px;
      font-weight: 700;
      color: #1d1d1f;
      margin-bottom: 6px;
      letter-spacing: -0.2px;
    }
    .summary-intro-subtitle {
      font-size: 13px;
      color: #6B6B6F;
      margin-bottom: 16px;
      font-weight: 500;
    }
    .summary-recommended-price {
      display: flex;
      align-items: center;
      gap: 12px;
      background: ${cardBg};
      border: 2px solid #28a745;
      border-radius: 12px;
      padding: 14px 16px;
      margin-top: 12px;
    }
    .summary-recommended-price:first-of-type {
      margin-top: 0;
    }
    .summary-recommended-price svg {
      flex-shrink: 0;
      color: #28a745;
      width: 24px;
      height: 24px;
    }
    .summary-recommended-price .content {
      flex: 1;
    }
    .summary-recommended-price .label {
      font-size: 12px;
      font-weight: 600;
      color: #34c759;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    .summary-recommended-price .trip-label {
      font-size: 14px;
      font-weight: 500;
      color: #6B6B6F;
    }
    .summary-recommended-price .price {
      font-size: 32px;
      font-weight: 800;
      color: #28a745;
      letter-spacing: -1px;
      line-height: 1;
    }

    .summary-section {
      padding: 20px;
    }
    .summary-section + .summary-section {
      border-top: 1px solid ${cardBorder};
    }
    #outbound-summary-section {
      border-left: 5px solid var(--color-outbound);
      background: linear-gradient(90deg, var(--color-outbound-lighter), var(--color-outbound-lighter), transparent);
    }
    #outbound-summary-section .section-title {
      color: var(--color-outbound);
    }
    #return-summary-section {
      border-left: 5px solid var(--color-return);
      background: linear-gradient(90deg, var(--color-return-lighter), var(--color-return-lighter), transparent);
    }
    #return-summary-section .section-title {
      color: var(--color-return);
    }

    .section-title {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 15px;
      font-weight: 700;
      color: var(--color-outbound);
      text-transform: uppercase;
      letter-spacing: 0.8px;
      margin-bottom: 16px;
    }
    .section-title svg {
      color: currentColor;
      width: 20px;
      height: 20px;
    }

    .route-info {
      background: linear-gradient(135deg, var(--color-outbound-lighter) 0%, var(--color-outbound-lighter) 100%);
      border: 1px solid var(--color-outbound-light);
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 16px;
    }

    #return-summary-section .route-info {
      background: linear-gradient(135deg, var(--color-return-lighter) 0%, var(--color-return-lighter) 100%);
      border: 1px solid var(--color-return-light);
    }

    .route-endpoints {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 12px;
    }
    .route-endpoints .endpoint {
      flex: 1;
      font-size: 17px;
      font-weight: 600;
      color: ${textPrimary};
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      letter-spacing: -0.4px;
    }
    .route-endpoints svg {
      flex-shrink: 0;
      color: #0A84FF;
      width: 18px;
      height: 18px;
    }

    .route-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 14px;
      color: #6B6B6F;
      font-weight: 600;
    }
    .route-meta .separator {
      color: #d1d1d6;
      font-weight: 400;
    }

    .prices-list {
      margin-top: 16px;
    }
    .prices-header {
      display: flex;
      justify-content: space-between;
      padding: 12px 16px;
      background: linear-gradient(135deg, rgba(40, 167, 69, 0.1) 0%, rgba(40, 167, 69, 0.05) 100%);
      border: 1px solid rgba(40, 167, 69, 0.18);
      border-radius: 12px;
      font-size: 13px;
      font-weight: 700;
      color: #28a745;
      margin-bottom: 10px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
    }
    .price-items {
      list-style: none;
      padding: 0;
      margin: 0;
      background: ${cardBg};
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid ${cardBorder};
      box-shadow: 0 2px 8px ${shadowColor};
    }
    .price-items li {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 18px;
      font-size: 16px;
      color: ${textPrimary};
      border-bottom: 0.5px solid ${cardBorder};
      font-weight: 500;
      letter-spacing: -0.3px;
      transition: background-color 0.2s ease;
    }
    .price-items li:hover {
      background: rgba(40, 167, 69, 0.03);
    }
    .price-items li:last-child {
      border-bottom: none;
    }
    .price-items li .price {
      font-weight: 800;
      color: #28a745;
      font-size: 22px;
      letter-spacing: -0.5px;
      text-shadow: 0 1px 2px rgba(40, 167, 69, 0.12);
    }

    .btn-validate-summary {
      margin: 20px auto;
      margin-top: 0;
      display: block;
      font-size: 18px;
      font-weight: 700;
      padding: 16px 24px;
      background: linear-gradient(135deg, #28a745 0%, #34c759 100%);
      box-shadow: 0 4px 16px rgba(40, 167, 69, 0.3), 0 2px 8px rgba(40, 167, 69, 0.18);
      border: none;
      letter-spacing: -0.3px;
    }
    .btn-validate-summary:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(40, 167, 69, 0.4), 0 3px 10px rgba(40, 167, 69, 0.25);
    }

    /* Wizard bar (Offer only) - full width, Apple-like */
    .offer-wizard-bar { 
      display: none; 
      flex-direction: column;
      gap: 0;
      padding: 2px 16px 0 16px; 
      margin: 0;
      position: relative;
    }
    /* Bouton retour style Apple - sur sa propre ligne */
    .offer-back-btn { 
      align-self: flex-start;
      z-index: 10;
      border: none;
      background: rgba(120, 120, 128, 0.16);
      color: var(--color-outbound);
      font-weight: 600;
      font-size: 15px;
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      padding: 8px 14px;
      border-radius: 10px;
      transition: all 0.2s ease;
      margin-bottom: 16px;
    }
    .offer-back-btn:hover { 
      background: rgba(120, 120, 128, 0.24);
      transform: translateX(-2px);
    }
    .offer-back-btn:active {
      background: rgba(120, 120, 128, 0.32);
      transform: scale(0.96);
    }
    .offer-back-btn svg {
      width: 20px;
      height: 20px;
    }
    /* Layout 4 étapes (par défaut, sans retour) */
    .offer-wizard-steps { 
      display: grid; 
      grid-template-columns: repeat(4,1fr); 
      gap: 8px; 
      width: 100%; 
      align-items: center;
      margin-bottom: 0;
    }
    .step-item { position:relative; display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:42px; }
    .step-item:not(:last-child)::after { content:""; position:absolute; top:13px; left:calc(50% + 18px); right:-50%; height:3px; background:#e5e7eb; border-radius:2px; }
    .step-item.done:not(:last-child)::after { background:var(--color-outbound); }
    /* En mode récurrent (4 étapes), pas de ligne après step-item-4 */
    .step-item.last-visible::after { display: none !important; }
    .step-badge { width:26px; height:26px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:14px; color:#6b7280; background:#e5e7eb; }
    .step-item.active .step-badge { background:var(--color-outbound); color:#fff; }
    .step-item.done .step-badge { background:#D1D1D6; color:#111; }
    .step-label { margin-top:4px; font-size:12px; color:#6b7280; font-weight:600; letter-spacing:-0.2px; }
    
    /* Layout 5 étapes (avec retour) - plus compact */
    .offer-wizard-steps.has-return { grid-template-columns: repeat(5,1fr); gap:6px; }
    .offer-wizard-steps.has-return .step-badge { width:24px; height:24px; font-size:13px; }
    .offer-wizard-steps.has-return .step-label { font-size:11px; }
    .offer-wizard-steps.has-return .step-item:not(:last-child)::after { left:calc(50% + 16px); }
    
    /* Layout 3 étapes (mode RSE) */
    .offer-wizard-steps.rse-mode { grid-template-columns: repeat(3,1fr); gap:10px; }
    
    .step-item.active .step-label { color:${textPrimary}; }
    .offer-page-title { 
      text-align: center; 
      font-weight: 800; 
      font-size: 22px; 
      letter-spacing: -0.3px; 
      color: ${textPrimary}; 
      margin: 0 16px 2px 16px;
      padding-top: 0;
    }

    /* Simple fade-slide animation */
    .fade-slide { opacity:0; transform: translateY(6px); transition: opacity .2s ease, transform .2s ease; }
    .fade-slide.visible { opacity:1; transform: translateY(0); }

  /* Premium slide pages between steps */
  .slide-page { will-change: transform, opacity; transition: transform .25s cubic-bezier(0.4, 0.0, 0.2, 1), opacity .25s cubic-bezier(0.4, 0.0, 0.2, 1); }
  .slide-off-left { transform: translateX(-24px); opacity: 0; }
  .slide-off-right { transform: translateX(24px); opacity: 0; }
  .slide-on { transform: translateX(0); opacity: 1; }

    /* Timelines (step 2) */
  .timelines-row { display:flex; gap:12px; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; }
    .tl-col { flex:1 1 320px; min-width:280px; }
  .tl-header { font-weight:800; font-size:16px; color:${textPrimary}; margin:4px 16px 6px 16px; letter-spacing:-0.2px; opacity:0.95; }
  .tl-date { font-size:13px; font-weight:500; color:${textSecondary}; margin:0 16px 8px 16px; letter-spacing:-0.1px; }
    .timeline-card {
      background: ${isDark ? 'rgba(28, 28, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)'};
      backdrop-filter: saturate(180%) blur(20px);
      -webkit-backdrop-filter: saturate(180%) blur(20px);
      border-radius: 18px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.08);
      margin: 8px 16px;
      border: 0.5px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'};
      padding: 12px 12px 6px 12px;
      position: relative;
      overflow: visible;
    }
    /* Desktop: reduce separation between the two cards and enlarge headers */
    @media (min-width: 900px) {
      .timelines-row { gap: 8px; }
      .timelines-row .timeline-card { margin: 8px 8px; }
      .tl-header { font-size: 18px; }
    }
    .tl-row { display:grid; grid-template-columns: 72px 18px 1fr; align-items:center; gap:10px; padding:8px 4px; }
    .tl-time { 
      font-weight:800; 
      font-size:16px; 
      color:${textPrimary}; 
      text-align:right; 
      position:relative; 
      display:flex; 
      flex-direction:column;
      align-items:flex-end;
      gap:2px;
    }
    .tl-time-main { font-weight:800; font-size:16px; color:${textPrimary}; line-height:1.2; font-variant-numeric: tabular-nums; }
    .tl-time, .route-meta-item span, .route-endpoints .endpoint, .summary-header { font-variant-numeric: tabular-nums; }
    .tl-date-compact { 
      font-size:11px; 
      font-weight:500; 
      color:${textSecondary}; 
      line-height:1.2;
      letter-spacing:-0.1px;
    }
    .tl-track { position:relative; display:flex; align-items:center; justify-content:center; height:100%; }
  .tl-dot { width:12px; height:12px; border-radius:50%; background:var(--color-outbound); box-shadow:0 1px 3px rgba(0,0,0,0.15); position:relative; z-index:2; }
    .tl-label { font-weight:600; color:${textPrimary}; font-size:15px; letter-spacing:-0.2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .tl-seg { display:grid; grid-template-columns: 72px 18px 1fr; align-items:center; gap:10px; padding:0 4px; }
  .tl-line { width:2px; background:linear-gradient(180deg, var(--color-outbound-lighter), var(--color-outbound)); position:relative; left:8px; height:24px; border-radius:2px; }
  .tl-spine { position:absolute; width:2px; background:linear-gradient(180deg, var(--color-outbound-lighter), var(--color-outbound)); border-radius:2px; left:0; top:0; height:0; pointer-events:none; z-index:1; }
    .tl-duration { grid-column: 3 / 4; font-size:12px; color:${textSecondary}; padding:4px 0 8px 0; }
  .tl-end .tl-dot { background:var(--color-outbound); }
  .tl-stop .tl-dot { background:#8E8E93; }
  /* Spine colors per card */
  #outbound-timeline .tl-spine { background: linear-gradient(180deg, var(--color-outbound-lighter), var(--color-outbound)); }
  /* Timeline retour en couleur return */
  #return-timeline .tl-dot { background:var(--color-return); }
  #return-timeline .tl-line { background:linear-gradient(180deg, var(--color-return-lighter), var(--color-return)); }
  #return-timeline .tl-spine { background: linear-gradient(180deg, var(--color-return-lighter), var(--color-return)); }
  #return-timeline .tl-end .tl-dot { background:var(--color-return); }
  
  /* Mode RSE : masquer les onglets */
  .tabs.rse-hidden { display: none !important; }
  
  /* Titre RSE au-dessus du wizard */
  .rse-title {
    padding: 24px 24px 16px 24px;
    text-align: center;
    background: ${isDark ? 'rgba(28, 28, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)'};
    border-bottom: 1px solid ${isDark ? '#2a2a2a' : '#f0f0f0'};
  }
  .rse-title h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 900;
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-family: ${this.fontFamily};
  }
  .rse-title p {
    margin: 8px 0 0 0;
    font-size: 15px;
    color: ${isDark ? '#a0a0a0' : '#8e8e93'};
    font-family: ${this.fontFamily};
  }
  </style>

  <div class="card">
    ${this.widgetMode === 'rse' ? `
      <div class="rse-title">
        <h1>🌱 Calculateur RSE</h1>
        <p>Renseignez votre trajet domicile-travail</p>
      </div>
    ` : ''}
    <div class="tabs ${this.widgetMode === 'rse' ? 'rse-hidden' : ''}" role="tablist">
      <button id="tab-find" class="tab ${this.activeTab === 'find' ? 'active' : ''}" role="tab" aria-selected="${this.activeTab === 'find'}">Trouver un covoit</button>
      <button id="tab-offer" class="tab ${this.activeTab === 'offer' ? 'active' : ''}" role="tab" aria-selected="${this.activeTab === 'offer'}">Proposer un covoit</button>
    </div>

    <!-- Wizard indicator (Offer only) -->
    <div id="offer-wizard-bar" class="offer-only offer-wizard-bar">
      <button id="offer-back-btn" class="offer-back-btn" type="button" style="display:none">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Retour
      </button>
      <div class="offer-wizard-steps">
        <div class="step-item" id="step-item-1"><div id="offer-step-1" class="step-badge" title="Saisie">1</div><div class="step-label">Saisie</div></div>
        <div class="step-item" id="step-item-2"><div id="offer-step-2" class="step-badge" title="Aller">2</div><div class="step-label">Aller</div></div>
        <div class="step-item" id="step-item-3"><div id="offer-step-3" class="step-badge" title="Retour">3</div><div class="step-label">Retour</div></div>
        <div class="step-item" id="step-item-4"><div id="offer-step-4" class="step-badge" title="Ajust.">4</div><div class="step-label">Ajust.</div></div>
        <div class="step-item" id="step-item-5"><div id="offer-step-5" class="step-badge" title="Récap">5</div><div class="step-label">Récap</div></div>
      </div>
    </div>
    <div id="offer-page-title" class="offer-only offer-page-title"></div>

  <!-- (Liste des offres déplacée sous les zones de saisie) -->

  <style>
  /* Apple/iOS-style unified search card */
  .search-card { 
    background: ${isDark ? 'rgba(28, 28, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)'}; 
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-radius: 18px; 
    box-shadow: 0 1px 3px ${shadowColor}, 0 8px 24px ${shadowColor}; 
    margin: 8px 16px; 
    overflow: hidden;
    border: 0.5px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'};
    scroll-margin-top: 250px;
  }
  .search-card .search-field { 
    display: flex; 
    align-items: center; 
    gap: 12px; 
    padding: 8px 12px;
    border-bottom: 0.5px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'};
    transition: background 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
    position: relative;
    min-height: 44px;
    scroll-margin-top: 250px;
  }
  .search-card .search-field:last-child { border-bottom: none; }
  .search-card .search-field:active { 
    background: ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)'};
    transition: background 0.05s;
  }
  @media (hover: hover) {
    .search-card .search-field:hover { 
      background: ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)'};
    }
  }
  .search-card .search-field .icon { 
    width: 24px; 
    height: 24px; 
    flex-shrink: 0;
    color: ${isDark ? '#98989d' : '#8e8e93'};
    display: flex;
    align-items: center;
    justify-content: center;
  }
  /* Ensure the svg inside the icon is constrained */
  .search-card .search-field .icon svg { 
    display: block; 
    width: 20px; 
    height: 20px; 
  }
  .search-card .search-field input[type="text"],
  .search-card .search-field select { 
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    outline: none; 
    font-size: 17px; 
    width: 100%;
    font-weight: 400;
    color: ${textPrimary};
    font-family: ${this.fontFamily};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    scroll-margin-top: 250px;
    padding: 0 !important;
    height: auto !important;
    border-radius: 0 !important;
  }
  .search-card .search-field input::placeholder {
    color: ${isDark ? '#636366' : '#c7c7cc'};
    font-weight: 400;
  }
  /* Pour le champ date - style iOS sans background */
  .search-card .search-field input[type="date"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    outline: none; 
    font-size: 17px;
    font-weight: 400;
    color: ${textPrimary};
    width: 100%;
    font-family: ${this.fontFamily};
    -webkit-font-smoothing: antialiased;
    scroll-margin-top: 250px;
    -webkit-appearance: none;
    appearance: none;
    padding: 0 !important;
    height: auto !important;
    border-radius: 0 !important;
  }
  /* Style pour le champ date retour (Find) - sans background ni bordure */
  .search-card .search-field input.return-date-placeholder[type="text"],
  .search-card .search-field input.date-placeholder[type="text"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    outline: none; 
    font-size: 17px;
    font-weight: 400;
    color: ${textPrimary};
    width: 100%;
    font-family: ${this.fontFamily};
    -webkit-font-smoothing: antialiased;
    scroll-margin-top: 250px;
    padding: 0 !important;
    height: auto !important;
    border-radius: 0 !important;
  }
  .search-card .search-field input.return-date-placeholder[type="text"]::placeholder,
  .search-card .search-field input.date-placeholder[type="text"]::placeholder {
    color: ${isDark ? '#636366' : '#8e8e93'};
    font-weight: 400;
  }
  
  /* Styles pour le sélecteur de jours (mode récurrent) */
  .days-selector {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .day-checkbox {
    position: relative;
    cursor: pointer;
    user-select: none;
  }
  .day-checkbox input[type="checkbox"] {
    position: absolute;
    opacity: 0;
    cursor: pointer;
  }
  .day-checkbox span {
    display: inline-block;
    padding: 8px 16px;
    border: 2px solid ${borderColor};
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    color: ${textSecondary};
    background: ${inputBg};
    transition: all 0.2s ease;
  }
  .day-checkbox input[type="checkbox"]:checked + span {
    background: ${this.colorOutbound};
    border-color: ${this.colorOutbound};
    color: white;
  }
  .day-checkbox:hover span {
    border-color: ${this.colorOutbound};
  }
  
  /* Styles pour les boutons RSE de modes de transport (jours de la semaine) */
  .rse-day-transport-btn:hover {
    transform: scale(1.05);
    border-color: ${this.colorOutbound} !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
  
  .rse-day-transport-btn:active {
    transform: scale(0.95) !important;
  }
  
  /* Style pour input time (mode récurrent) */
  .search-card .search-field input[type="time"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    outline: none; 
    font-size: 17px;
    font-weight: 400;
    color: ${textPrimary};
    font-family: ${this.fontFamily};
    -webkit-font-smoothing: antialiased;
  }
  
  /* Séparateur vertical style iOS */
  .search-card .search-field .divider {
    width: 0.5px;
    height: 24px;
    background: ${isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.1)'};
    margin: 0 4px;
  }
  
  /* Style moderne pour le slider de rayon */
  #radius-km {
    -webkit-appearance: none;
    appearance: none;
  }
  #radius-km::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--color-outbound) 0%, var(--color-outbound) 100%);
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4), 0 0 0 4px rgba(124, 58, 237, 0.1);
    transition: all 0.2s ease;
  }
  #radius-km::-webkit-slider-thumb:hover {
    transform: scale(1.1);
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.5), 0 0 0 6px rgba(124, 58, 237, 0.15);
  }
  #radius-km::-moz-range-thumb {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--color-outbound) 0%, var(--color-outbound) 100%);
    cursor: pointer;
    border: none;
    box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4), 0 0 0 4px rgba(124, 58, 237, 0.1);
    transition: all 0.2s ease;
  }
  #radius-km::-moz-range-thumb:hover {
    transform: scale(1.1);
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.5), 0 0 0 6px rgba(124, 58, 237, 0.15);
  }
  
  /* Responsive: sur mobile, compacter pour garder tout sur une ligne */
  @media (max-width: 768px) {
    /* Réduire les marges de la card */
    .search-card {
      margin: 8px 8px;
    }
    
    /* Réduire le padding des search-fields */
    .search-card .search-field {
      padding: 10px 8px;
      gap: 6px;
    }
    
    /* Réduire la taille des icônes */
    .search-card .search-field .icon {
      width: 20px;
      height: 20px;
    }
    .search-card .search-field .icon svg {
      width: 18px;
      height: 18px;
    }
    
    /* Réduire les marges du divider */
    .search-card .search-field .divider {
      margin: 0 2px;
      height: 20px;
    }
    
    /* Compacter les inputs date/select */
    .search-card .search-field input[type="date"],
    .search-card .search-field select.time-select {
      font-size: 15px;
      min-width: 0;
      flex: 1 1 auto;
    }
    
    /* Réduire le padding global du widget sur mobile */
    :host {
      padding: 16px 8px;
    }
  }
  /* Time display and custom picker */
  .time-display {
    position: absolute;
    inset: 0;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    padding: 8px 10px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    color: ${textPrimary};
    font-weight: 600;
    cursor: pointer;
  }
  .time-picker-panel {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.18);
    z-index: 20000;
    padding: 10px;
  }
  .time-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; max-height: 200px; overflow: auto; }
  .time-btn { padding: 8px 10px; border: 1px solid #e5e7eb; border-radius: 8px; background:#f9fafb; cursor:pointer; text-align:center; font-weight:600; }
  .time-actions { display:flex; gap:8px; margin-bottom:8px; }
  .time-action { flex:1; padding:8px; border:1px solid #e5e7eb; border-radius:8px; background:#f3f4f6; cursor:pointer; font-weight:600; text-align:center; }
  .time-input { width: 100%; padding:8px; border:1px solid #e5e7eb; border-radius:8px; margin-top:8px; }
  .loading-panel { display:flex; align-items:center; gap:10px; background:#fff; border:1px solid #e5e7eb; border-radius:12px; box-shadow:0 4px 12px rgba(0,0,0,0.08); padding:14px; margin:0 auto; }
  .spinner { width:18px; height:18px; border:2px solid #e5e7eb; border-top-color: var(--color-outbound); border-radius:50%; animation: spin 0.8s linear infinite; }
  .loading-text { font-size:14px; color:${textPrimary}; font-weight:600; }
  @keyframes spin { from { transform: rotate(0deg);} to { transform: rotate(360deg);} }
  /* Center loading panels horizontally and vertically */
  #find-loading, #recurrent-loading { display:flex; align-items:center; justify-content:center; width:100%; }
  /* Center only during loading */
  #find-results-region.is-loading, #recurrent-results-region.is-loading { align-items:center; justify-content:center; }
  </style>

  <div class="form">
  ${(this.isRecurrentMode() || this.isRseMode()) ? '' : `
  <!-- Header pour afficher le nombre de trajets disponibles (Find only) - masqué en mode récurrent -->
  <div id="find-header" class="find-only" style="display: none; margin-bottom: 20px; text-align: center; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 22px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);">
    <p id="find-header-subtitle" style="margin: 0 0 10px 0; font-size: 18px; color: #1f2937; font-weight: 700; font-family:${this.fontFamily}; line-height: 1.4;">
      ${this.eventName 
        ? `Trouve ton covoit pour <span style="color: var(--color-outbound, #6366f1);">${this.eventName}</span> ! 🚗`
        : `🎯 Trouvez un covoiturage pour cet évènement`}
    </p>
    <div id="find-header-count" style="display: inline-block; margin: 0; font-size: 13px; font-weight: 600; color: #6b7280; font-family:${this.fontFamily}; background: #f3f4f6; border-radius: 100px; padding: 4px 14px;">— trajets</div>
  </div>
  `}
  
  <!-- Header étape 1: Saisie du trajet -->
  <div id="step1-header" class="offer-only" style="display: none; margin: 16px 0 20px 0; text-align: center;">
    <p style="margin: 0; font-size: 15px; color: #6B6B6F; font-weight: 600;font-family:${this.fontFamily};">Renseignez les informations du covoiturage que vous souhaitez proposer</p>
  </div>
  <div class="search-card" style="margin-bottom:0;">
        <!-- Départ -->
        <div class="search-field">
          <span class="icon" aria-hidden="true" title="Départ">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 22s7-7.58 7-12a7 7 0 1 0-14 0c0 4.42 7 12 7 12Z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="10" r="3" stroke="currentColor" stroke-width="2"/></svg>
          </span>
          <input id="from" type="text" autocomplete="off" placeholder="Départ" />
          <datalist id="from-suggestions"></datalist>
        </div>

        <!-- Rayon fixe pour tous les modes -->
        <input type="hidden" id="radius-km" value="50" />

        <!-- Destination -->
        ${this.companySites.length > 0 ? `
        <!-- Sélecteur de site (mode B2B - Offer) -->
        <div class="search-field offer-only">
          <span class="icon" aria-hidden="true" title="Site">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 22s7-7.58 7-12a7 7 0 1 0-14 0c0 4.42 7 12 7 12Z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="10" r="3" stroke="currentColor" stroke-width="2"/></svg>
          </span>
          <select id="site-selector" style="flex: 1;">
            <option value="">Sélectionnez votre site</option>
            ${this.companySites.map(site => `
              <option value="${site.id}" data-address="${site.site_address}">${site.site_name}</option>
            `).join('')}
          </select>
        </div>
        
        <!-- Sélecteur de site (mode B2B - Find) -->
        <div class="search-field find-only">
          <span class="icon" aria-hidden="true" title="Site">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 22s7-7.58 7-12a7 7 0 1 0-14 0c0 4.42 7 12 7 12Z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="10" r="3" stroke="currentColor" stroke-width="2"/></svg>
          </span>
          <select id="site-selector-find" style="flex: 1;">
            <option value="">Site de destination</option>
            ${this.companySites.map(site => `
              <option value="${site.id}" data-address="${site.site_address}">${site.site_name}</option>
            `).join('')}
          </select>
        </div>
        
        <!-- Champ destination caché (sera rempli auto) -->
        <input type="hidden" id="to" value="" />
        ` : `
        <!-- Saisie libre de destination (mode classique) -->
        <div class="search-field">
          <span class="icon" aria-hidden="true" title="Destination">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 22s7-7.58 7-12a7 7 0 1 0-14 0c0 4.42 7 12 7 12Z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="10" r="3" stroke="currentColor" stroke-width="2"/></svg>
          </span>
          <input id="to" type="text" autocomplete="off" placeholder="Destination" />
          <datalist id="to-suggestions"></datalist>
        </div>
        `}

        <!-- Date/Heure (Mode Ponctuel) OU Jours + Heure (Mode Récurrent/RSE) -->
        ${this.isRecurrentMode() || this.widgetMode === 'rse' ? `
        <!-- Mode Récurrent/RSE: Sélecteur de jours (Offer) -->
        <div class="search-field offer-only">
          ${this.widgetMode === 'rse' ? '' : `
          <span class="icon" aria-hidden="true" title="Jours">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/><path d="M16 2v4M8 2v4M3 10h18" stroke="currentColor" stroke-width="2"/></svg>
          </span>
          `}
          <div style="flex: 1;">
            <div style="font-size: 15px; font-weight: 500; color: ${this.widgetMode === 'rse' ? textSecondary : textPrimary}; margin-bottom: 8px; ${this.widgetMode === 'rse' ? 'text-align: center;' : ''}">${this.widgetMode === 'rse' ? 'Vos modes de transport' : 'Jours de covoiturage'}</div>
            ${this.widgetMode === 'rse' ? `
            <!-- Mode RSE: Sélecteur de modes de transport par jour du mois -->
            <div id="rse-transport-calendar" style="display: flex; flex-direction: column; gap: 4px; max-height: 300px; overflow-y: auto;">
              <!-- Les jours du mois seront générés ici dynamiquement -->
            </div>
            ` : `
            <!-- Mode Récurrent classique: Jours de la semaine -->
            <div class="days-selector" style="display: flex; gap: 6px; flex-wrap: wrap;">
              <label class="day-checkbox">
                <input type="checkbox" name="monday" id="day-monday" />
                <span>Lun</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="tuesday" id="day-tuesday" />
                <span>Mar</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="wednesday" id="day-wednesday" />
                <span>Mer</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="thursday" id="day-thursday" />
                <span>Jeu</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="friday" id="day-friday" />
                <span>Ven</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="saturday" id="day-saturday" />
                <span>Sam</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="sunday" id="day-sunday" />
                <span>Dim</span>
              </label>
            </div>
            `}
          </div>
        </div>

        <!-- Mode Récurrent: Heure aller (pas pour RSE) -->
        ${this.isRecurrentMode() ? `
        <div class="search-field offer-only">
          <span class="icon" aria-hidden="true" title="Heure aller">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="9" stroke="${this.colorOutbound}" stroke-width="2"/>
              <path d="M12 6v6l4 2" stroke="${this.colorOutbound}" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </span>
          <div style="flex: 1; display: flex; flex-direction: column; gap: 2px;">
            <span style="font-size: 15px; font-weight: 500; color: ${textPrimary};">Heure d'arrivée</span>
            <span style="font-size: 12px; color: ${textTertiary};">Heure habituelle indicative d'arrivée sur site</span>
          </div>
          <input type="time" id="recurrent-time-outbound" value="08:00" style="width: 90px;" />
        </div>

        <!-- Mode Récurrent: Heure retour (pas pour RSE) -->
        <div class="search-field offer-only">
          <span class="icon" aria-hidden="true" title="Heure retour">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="9" stroke="${this.colorReturn}" stroke-width="2"/>
              <path d="M12 6v6l4 2" stroke="${this.colorReturn}" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </span>
          <div style="flex: 1; display: flex; flex-direction: column; gap: 2px;">
            <span style="font-size: 15px; font-weight: 500; color: ${textPrimary};">Heure de départ</span>
            <span style="font-size: 12px; color: ${textTertiary};">Heure habituelle indicative de départ du site</span>
          </div>
          <input type="time" id="recurrent-time-return" value="18:00" style="width: 90px;" />
        </div>
        ` : ''}
        ` : this.isRseMode() ? `
        <!-- Mode RSE: Sélecteur de jours (Offer) -->
        <div class="search-field offer-only">
          <span class="icon" aria-hidden="true" title="Jours">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/><path d="M16 2v4M8 2v4M3 10h18" stroke="currentColor" stroke-width="2"/></svg>
          </span>
          <div style="flex: 1;">
            <div style="font-size: 15px; font-weight: 500; color: ${textPrimary}; margin-bottom: 8px;">Jours de covoiturage</div>
            <div class="days-selector" style="display: flex; gap: 6px; flex-wrap: wrap;">
              <label class="day-checkbox">
                <input type="checkbox" name="monday" id="day-monday" />
                <span>Lun</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="tuesday" id="day-tuesday" />
                <span>Mar</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="wednesday" id="day-wednesday" />
                <span>Mer</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="thursday" id="day-thursday" />
                <span>Jeu</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="friday" id="day-friday" />
                <span>Ven</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="saturday" id="day-saturday" />
                <span>Sam</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" name="sunday" id="day-sunday" />
                <span>Dim</span>
              </label>
            </div>
          </div>
        </div>
        ` : `
        <!-- Mode Ponctuel: Date + Heure aller (Offer only) -->
        <div class="search-field offer-only">
          <span class="icon" aria-hidden="true" title="Date">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/><path d="M16 2v4M8 2v4M3 10h18" stroke="currentColor" stroke-width="2"/></svg>
          </span>
          <input type="date" id="date" placeholder="Aujourd'hui" style="flex: 1;" />
        </div>
        
        <!-- Champ caché pour l'heure (sera utilisé pour les calculs internes) -->
        <input type="hidden" id="from-time" value="09:00" />
        `}

        ${(this.isRecurrentMode() || this.isRseMode()) ? '' : `
        <!-- Nombre de passagers (tous les onglets) - masqué en mode récurrent -->
        <div class="search-field">
          <span class="icon" aria-hidden="true" title="Places disponibles">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/><path d="M3 21v-2a4 4 0 014-4h10a4 4 0 014 4v2" stroke="currentColor" stroke-width="2"/></svg>
          </span>
          <div style="flex: 1; display: flex; flex-direction: column; gap: 2px;">
            <span style="font-size: 15px; font-weight: 500; color: ${textPrimary};">Places disponibles</span>
            <span style="font-size: 12px; color: ${textTertiary};">Nombre de passagers que vous pouvez embarquer</span>
          </div>
          <select id="seats" style="width: 60px;">
            <option value="1" selected>1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5</option>
            <option value="6">6</option>
            <option value="7">7</option>
            <option value="8">8</option>
            <option value="9">9</option>
            <option value="10">10</option>
          </select>
        </div>
        `}
        ${(this.isRecurrentMode() || this.isRseMode()) ? '<input type="hidden" id="seats" value="1" />' : ''}

        <!-- Bouton Rechercher (onglet Trouver) - intégré dans la search-card -->
        <div class="search-field find-only" style="background:var(--color-outbound);border:none;padding:8px 12px;cursor:pointer;transition:all 0.2s;" onmouseover="this.style.opacity='0.9'" onmouseout="this.style.opacity='1'">
          <button id="validate" style="width:100%;background:transparent;border:none;color:white;font-weight:700;font-size:16px;cursor:pointer;padding:0;margin:0;font-family:inherit;">
            Rechercher
          </button>
        </div>

        <!-- Champ caché pour max-detour-km (sera rempli en page 5) -->
        <input type="hidden" id="max-detour-km" value="5" />
        <!-- Champ caché pour max-detour-time en minutes (prioritaire sur la distance) -->
        <input type="hidden" id="max-detour-time" value="25" />

        ${(this.isRecurrentMode() || this.isRseMode()) ? '' : `
        <!-- Trajet retour (toggle iOS intégré - offre uniquement - MODE PONCTUEL SEULEMENT) -->
        <div class="search-field return-toggle-field offer-only">
          <span class="icon" aria-hidden="true" title="Trajet retour">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 14l-4-4m0 0l4-4m-4 4h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          </span>
          <span style="font-size: 17px; flex: 1; font-family: ${this.fontFamily}; color: ${textPrimary};">Trajet retour</span>
          <label class="switch-ios">
            <input type="checkbox" id="return" />
            <span class="switch-ios-slider"></span>
          </label>
        </div>

        <!-- Options retour (collapsible) -->
        <div id="return-options" class="return-options offer-only" style="display: none;">
          <div class="search-field">
            <span class="icon" aria-hidden="true" title="Date retour">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/><path d="M16 2v4M8 2v4M3 10h18" stroke="currentColor" stroke-width="2"/></svg>
            </span>
            <input type="date" id="return-date-offer" placeholder="Date et heure du départ retour" style="flex: 1;" />
            <span class="divider" role="separator" aria-hidden="true"></span>
            <span class="icon" id="return-time-icon" aria-hidden="true" title="Heure retour">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <!-- Horloge -->
                <circle cx="10" cy="14" r="9" stroke="currentColor" stroke-width="2"/>
                <path d="M10 8v6l4 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <!-- Flèche sortante (plus grande) -->
                <path d="M17 7l6-6m0 0h-4m4 0v4" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </span>
            <div style="position: relative; flex: 1;">
              <select id="return-time" style="width: 100%;">
                ${this.generateTimeOptions()}
              </select>
              <div id="return-time-display" class="time-display" role="button" aria-label="Modifier l'heure de retour"></div>
              <span style="position: absolute; top: -22px; right: 0; font-size: 10px; color: #8E8E93; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;font-family:${this.fontFamily};">Date et heure du départ retour</span>
            </div>
          </div>
          
          <!-- Nombre de passagers retour -->
          <div class="search-field">
            <span class="icon" aria-hidden="true" title="Passagers retour">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/><path d="M3 21v-2a4 4 0 014-4h10a4 4 0 014 4v2" stroke="currentColor" stroke-width="2"/></svg>
            </span>
            <select id="seats-return">
              <option value="1">1 passager</option>
              <option value="2">2 passagers</option>
              <option value="3">3 passagers</option>
              <option value="4" selected>4 passagers</option>
              <option value="5">5 passagers</option>
              <option value="6">6 passagers</option>
              <option value="7">7 passagers</option>
              <option value="8">8 passagers</option>
              <option value="9">9 passagers</option>
              <option value="10">10 passagers</option>
            </select>
          </div>
        </div>
        `}
  </div>

        <!-- (date + seats + car-type déplacés en haut) -->

        <!-- Bouton Confirmer mon trajet (étape 1 : passe à l'étape 2) -->
        <div id="confirm-trip-wrapper" class="offer-only fade-slide" style="margin: 16px;">
          <button id="confirm-trip-btn" class="btn-calculate">
            Voir les itinéraires
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-left: 8px;">
              <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>

        <!-- Sélection de trajet (étape 2 : NOUVEAU) -->
        <div id="route-selection-wrapper" class="offer-only fade-slide" style="display:none; margin: 16px;">
          <div id="route-selection-header">
            <!-- L'en-tête sera injecté dynamiquement selon l'étape (aller/retour) -->
          </div>
          <div id="route-alternatives-list">
            <!-- Les alternatives seront injectées ici -->
          </div>
        </div>

        <!-- (Récapitulatif déplacé sous la carte) -->

        </div>
    <!-- Zone résultats (onglet Trouver) -->
    <div id="find-results-region" class="find-only keep-display" style="display:flex;flex:1 1 auto;align-items:flex-start;justify-content:flex-start;padding:4px 12px;">
      <!-- Liste des offres -->
      <div id="find-offers" style="display:none;width:100%;padding:4px 12px 12px 12px;">
        <div id="find-offers-inner" class="offers-list" aria-live="polite" aria-busy="false" style="display:grid;gap:10px;"></div>
      </div>
    </div>
    
    <!-- Résultats de recherche récurrente (onglet Trouver - mode récurrent) -->
    <div id="recurrent-results-region" class="find-only keep-display" style="display:flex;flex:1 1 auto;align-items:flex-start;justify-content:flex-start;padding:4px 12px;">
      <div id="recurrent-search-results" style="display:none;width:100%;padding:4px 12px 12px 12px;">
        <div id="recurrent-search-results-inner" style="display:grid;gap:12px;"></div>
      </div>
    </div>
    
    <!-- Mes trajets (onglet dédié) -->
    <div id="my-trips" class="mine-only" style="display:none;padding:4px 12px 12px 12px;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin:0 0 8px 0;gap:12px;flex-wrap:wrap;">
        <div style="font-weight:700;font-family:${this.fontFamily};">Mes trajets</div>
      </div>
      
      <!-- Carte pour afficher l'itinéraire sélectionné -->
      <div id="my-trips-map-container" style="display:none;margin-bottom:16px;">
        <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <div style="padding:12px;background:#fff;border-bottom:1px solid #e5e7eb;">
            <div style="display:flex;align-items:center;justify-content:space-between;">
              <div style="font-weight:700;font-size:14px;font-family:${this.fontFamily};">📍 Itinéraire</div>
              <button id="close-my-trips-map" style="background:none;border:none;cursor:pointer;padding:4px;font-size:20px;color:#6b7280;">×</button>
            </div>
          </div>
          <div id="my-trips-map" style="width:100%;height:350px;"></div>
          <div id="my-trips-timeline" style="padding:12px;background:#fff;border-top:1px solid #e5e7eb;"></div>
        </div>
      </div>
      
      <div style="display:flex;flex-direction:column;gap:14px;">
        <div>
          <div style="font-weight:700;margin:2px 0 6px 0;font-family:${this.fontFamily};">Mes offres</div>
          <div id="my-offers-inner" class="offers-list" style="display:grid;gap:10px;"></div>
        </div>
        <div>
          <div style="font-weight:700;margin:6px 0 6px 0;font-family:${this.fontFamily};">Mes réservations</div>
          <div id="my-reservations-inner" class="offers-list" style="display:grid;gap:10px;"></div>
        </div>
      </div>
    </div>
    
    <!-- Header étape 4: Récapitulatif du trajet -->
    <div id="step4-header" class="offer-only" style="display: none; margin: 16px 16px 24px 16px; text-align: center; background: ${isDark ? 'linear-gradient(135deg, #2a2a2a 0%, #1a1a1a 100%)' : 'linear-gradient(135deg, #F5F5F7 0%, #E8E8EA 100%)'}; border-radius: 16px; padding: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);">
      <div style="display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 8px;">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M9 11l3 3 8-8" stroke="#34C759" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="12" cy="12" r="10" stroke="${textSecondary}" stroke-width="2.5"/>
        </svg>
        <h3 style="margin: 0; font-size: 28px; font-weight: 900; color: ${textPrimary}; letter-spacing: -0.02em;font-family:${this.fontFamily};">Récapitulatif du trajet</h3>
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2v20M5 12h14" stroke="${textSecondary}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="12" cy="7" r="2" fill="${textSecondary}"/>
          <circle cx="12" cy="17" r="2" fill="${textSecondary}"/>
        </svg>
      </div>
      <p style="margin: 0; font-size: 15px; color: ${textSecondary}; font-weight: 500;font-family:${this.fontFamily};">Vérifiez les détails de votre trajet avant de publier</p>
      <div id="departure-time-info" style="margin-top: 12px; padding: 12px; background: var(--color-outbound-lighter); border-radius: 12px; border-left: 4px solid var(--color-outbound);">
        <div style="font-size: 13px; color: ${textSecondary}; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;font-family:${this.fontFamily};">🚗 Heure de départ recommandée</div>
        <div id="calculated-departure-time" style="font-size: 24px; font-weight: 700; color: var(--color-outbound);font-family:${this.fontFamily};">--:--</div>
      </div>
    </div>
    </div>
    
    <!-- Timelines estimées (étape 2 - au-dessus de la carte) -->
    <div id="timelines-wrap" class="offer-only fade-slide" style="display:none;">
      <div class="timelines-row">
        <div class="tl-col">
          <div class="tl-header">Aller</div>
          <div class="tl-date" id="outbound-date" style="display: none;"></div>
          <div id="outbound-timeline" class="timeline-card"></div>
        </div>
        <div class="tl-col" id="ret-col" style="display:none;">
          <div class="tl-header">Retour</div>
          <div class="tl-date" id="return-date" style="display: none;"></div>
          <div id="return-timeline" class="timeline-card"></div>
        </div>
      </div>
    </div>

    <!-- Carte (cachée initialement en mode Proposer) -->
    <div class="map-box fade-slide" id="map-box-container">
      <!-- Checkbox point de rencontre (mode Find récurrent) -->
      <div id="meeting-point-checkbox" style="display: none; margin: 0 16px 12px 16px; padding: 12px; background: linear-gradient(135deg, #d1fae5, #a7f3d0); border: 2px solid #10b981; border-radius: 12px; font-family: ${this.fontFamily};">
        <label style="display: flex; align-items: center; gap: 12px; cursor: pointer;">
          <input type="checkbox" id="use-meeting-point" style="width: 20px; height: 20px; cursor: pointer; accent-color: #10b981;">
          <div style="flex: 1;">
            <div style="font-size: 14px; font-weight: 700; color: #047857; margin-bottom: 4px;">✅ Point de rencontre sans détour</div>
            <div id="meeting-point-address" style="font-size: 12px; color: #065f46;">📍 <strong>Adresse du point</strong></div>
            <div style="font-size: 11px; color: #065f46; margin-top: 4px; font-style: italic;">Cochez pour vous rendre à ce point et ne pas créer de détour</div>
          </div>
        </label>
      </div>
      <div class="map" id="map"></div>
      <div id="map-loading" class="map-loading" hidden>
        <div class="spinner" aria-label="Chargement de l'itinéraire"></div>
      </div>
    </div>
    <div class="legend fade-slide" id="map-legend">
      <div class="legend-item"><span class="legend-line"></span> Aller</div>
      <div class="legend-item"><span class="legend-line-return"></span> Retour</div>
    </div>
    <!-- Bouton Calculer l'itinéraire déplacé sous la carte (étape 2) -->
    <div id="calculate-btn-wrapper" class="offer-only fade-slide" style="margin: 16px; display: none;">
      <button id="calculate-route-btn" class="btn-calculate">
        Calculer l'itinéraire
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-left: 8px;">
          <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </div>
    <!-- Encart récapitulatif (désormais sous la carte) -->
  <div id="trip-summary" class="offer-only trip-summary fade-slide" style="display: none; margin-top:8px;">
      <div class="summary-header">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M9 11l3 3 8-8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span style="flex: 1;">Votre trajet est prêt !</span>
        <button id="edit-route-btn" style="background: rgba(255, 255, 255, 0.25); border: 1px solid rgba(255, 255, 255, 0.4); color: #fff; font-size: 14px; cursor: pointer; padding: 6px 12px; font-weight: 600; border-radius: 8px; transition: all 0.2s ease; backdrop-filter: blur(10px);font-family:${this.fontFamily};" onmouseover="this.style.background='rgba(255, 255, 255, 0.35)'" onmouseout="this.style.background='rgba(255, 255, 255, 0.25)'">
          ✏️ Modifier
        </button>
      </div>
      <!-- Jours de covoiturage et impact CO2 -->
      <div class="summary-intro">
        <div class="summary-intro-title">Récapitulatif du trajet</div>
        <div class="summary-intro-subtitle">Vérifiez les détails de votre trajet avant de publier</div>
        
        <!-- Jours sélectionnés avec badges comme page 1 (mode récurrent uniquement) -->
        <div id="summary-recurrent-days" style="display: none; margin-top: 16px; padding: 16px; background: linear-gradient(135deg, rgba(10, 132, 255, 0.06) 0%, rgba(10, 132, 255, 0.02) 100%); border: 1px solid rgba(10, 132, 255, 0.15); border-radius: 12px;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="3" y="4" width="18" height="18" rx="2" stroke="${this.colorOutbound}" stroke-width="2"/>
              <path d="M16 2v4M8 2v4M3 10h18" stroke="${this.colorOutbound}" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span style="font-size: 14px; font-weight: 600; color: #1d1d1f; font-family: ${this.fontFamily};">Jours de covoiturage</span>
          </div>
          <div id="summary-days-badges" style="display: flex; flex-wrap: wrap; gap: 8px;"></div>
        </div>
        
        <!-- Date du trajet (mode ponctuel uniquement) -->
        <div id="summary-ponctual-date" style="display: none; margin-top: 16px; padding: 16px; background: linear-gradient(135deg, rgba(10, 132, 255, 0.06) 0%, rgba(10, 132, 255, 0.02) 100%); border: 1px solid rgba(10, 132, 255, 0.15); border-radius: 12px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="3" y="4" width="18" height="18" rx="2" stroke="${this.colorOutbound}" stroke-width="2"/>
              <path d="M16 2v4M8 2v4M3 10h18" stroke="${this.colorOutbound}" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span style="font-size: 14px; font-weight: 600; color: #1d1d1f; font-family: ${this.fontFamily};">Date du trajet</span>
            <span id="summary-date-display" style="font-size: 14px; font-weight: 700; color: ${this.colorOutbound}; font-family: ${this.fontFamily}; margin-left: auto;"></span>
          </div>
        </div>
      </div>
      
      <!-- Schéma visuel du trajet (style email) -->
      <div class="summary-section" style="margin: 20px; padding: 20px; background: ${bgPrimary}; border-radius: 14px; border: 1px solid ${inputBorder};">
        <!-- Trajet Aller -->
        <div id="outbound-summary-visual">
          <div style="display: flex; align-items: flex-start; gap: 16px;">
            <!-- Ligne verticale avec points -->
            <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
              <div style="width: 12px; height: 12px; border-radius: 50%; background: ${this.colorOutbound}; border: 3px solid ${bgPrimary}; box-shadow: 0 0 0 2px ${this.colorOutbound};"></div>
              <div style="width: 2px; flex: 1; min-height: 40px; background: linear-gradient(to bottom, ${this.colorOutbound}, ${this.colorOutbound}); opacity: 0.3;"></div>
              <div style="width: 12px; height: 12px; border-radius: 50%; background: ${this.colorOutbound}; border: 3px solid ${bgPrimary}; box-shadow: 0 0 0 2px ${this.colorOutbound};"></div>
            </div>
            <!-- Infos du trajet -->
            <div style="flex: 1; min-width: 0;">
              <div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                  <div style="font-size: 12px; font-weight: 600; color: ${this.colorOutbound}; text-transform: uppercase; letter-spacing: 0.5px; font-family: ${this.fontFamily};">Départ</div>
                  <div id="summary-time-out-depart" style="font-size: 13px; font-weight: 700; color: ${this.colorOutbound}; font-family: ${this.fontFamily};"></div>
                </div>
                <div id="summary-from" style="font-size: 15px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily}; word-wrap: break-word;">Adresse de départ</div>
              </div>
              <div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                  <div style="font-size: 12px; font-weight: 600; color: ${this.colorOutbound}; text-transform: uppercase; letter-spacing: 0.5px; font-family: ${this.fontFamily};">Arrivée</div>
                  <div id="summary-time-out-arrivee" style="font-size: 13px; font-weight: 700; color: ${this.colorOutbound}; font-family: ${this.fontFamily};"></div>
                </div>
                <div id="summary-to" style="font-size: 15px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily}; word-wrap: break-word;">Adresse d'arrivée</div>
              </div>
              <div style="margin-top: 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: rgba(10, 132, 255, 0.08); border-radius: 8px;">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" stroke="${this.colorOutbound}" stroke-width="2"/>
                    <circle cx="12" cy="10" r="3" stroke="${this.colorOutbound}" stroke-width="2"/>
                  </svg>
                  <span id="summary-distance-out" style="font-size: 13px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily};">0 km</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: rgba(10, 132, 255, 0.08); border-radius: 8px;">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="8" r="3" stroke="${this.colorOutbound}" stroke-width="2"/>
                    <path d="M12 14c-4 0-7 2-7 4v2h14v-2c0-2-3-4-7-4z" stroke="${this.colorOutbound}" stroke-width="2"/>
                  </svg>
                  <span id="summary-seats-out" style="font-size: 13px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily};">4 places</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Trajet Retour (si activé) -->
        <div id="return-summary-visual" style="display: none; margin-top: 24px; padding-top: 24px; border-top: 2px dashed ${inputBorder};">
          <div style="display: flex; align-items: flex-start; gap: 16px;">
            <!-- Ligne verticale avec points -->
            <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
              <div style="width: 12px; height: 12px; border-radius: 50%; background: ${this.colorReturn}; border: 3px solid ${bgPrimary}; box-shadow: 0 0 0 2px ${this.colorReturn};"></div>
              <div style="width: 2px; flex: 1; min-height: 40px; background: linear-gradient(to bottom, ${this.colorReturn}, ${this.colorReturn}); opacity: 0.3;"></div>
              <div style="width: 12px; height: 12px; border-radius: 50%; background: ${this.colorReturn}; border: 3px solid ${bgPrimary}; box-shadow: 0 0 0 2px ${this.colorReturn};"></div>
            </div>
            <!-- Infos du trajet -->
            <div style="flex: 1; min-width: 0;">
              <div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                  <div style="font-size: 12px; font-weight: 600; color: ${this.colorReturn}; text-transform: uppercase; letter-spacing: 0.5px; font-family: ${this.fontFamily};">Départ</div>
                  <div id="summary-time-ret-depart" style="font-size: 13px; font-weight: 700; color: ${this.colorReturn}; font-family: ${this.fontFamily};"></div>
                </div>
                <div id="summary-to-ret" style="font-size: 15px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily}; word-wrap: break-word;">Adresse de départ</div>
              </div>
              <div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                  <div style="font-size: 12px; font-weight: 600; color: ${this.colorReturn}; text-transform: uppercase; letter-spacing: 0.5px; font-family: ${this.fontFamily};">Arrivée</div>
                  <div id="summary-time-ret-arrivee" style="font-size: 13px; font-weight: 700; color: ${this.colorReturn}; font-family: ${this.fontFamily};"></div>
                </div>
                <div id="summary-from-ret" style="font-size: 15px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily}; word-wrap: break-word;">Adresse d'arrivée</div>
              </div>
              <div style="margin-top: 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: rgba(255, 69, 58, 0.08); border-radius: 8px;">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" stroke="${this.colorReturn}" stroke-width="2"/>
                    <circle cx="12" cy="10" r="3" stroke="${this.colorReturn}" stroke-width="2"/>
                  </svg>
                  <span id="summary-distance-ret" style="font-size: 13px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily};">0 km</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: rgba(255, 69, 58, 0.08); border-radius: 8px;">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="8" r="3" stroke="${this.colorReturn}" stroke-width="2"/>
                    <path d="M12 14c-4 0-7 2-7 4v2h14v-2c0-2-3-4-7-4z" stroke="${this.colorReturn}" stroke-width="2"/>
                  </svg>
                  <span id="summary-seats-ret" style="font-size: 13px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily};">4 places</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Carte avec visualisation des buffers -->
      <div id="summary-map-container" style="width: 100%; border-radius: 0; overflow: hidden;">
        <div id="summary-map" style="width: 100%; height: 400px;"></div>
      </div>
      
      <!-- Contrôle du buffer de temps avec checkbox pour accepter les détours -->
      <div id="summary-detour-control" style="margin: 20px; padding: 18px; background: linear-gradient(135deg, rgba(10, 132, 255, 0.08) 0%, rgba(10, 132, 255, 0.02) 100%); border: 1px solid rgba(10, 132, 255, 0.2); border-radius: 14px;">
        <div style="display: flex; align-items: flex-start; gap: 14px; margin-bottom: 20px;">
          <input type="checkbox" id="summary-accept-detours" checked style="width: 20px; height: 20px; cursor: pointer; margin-top: 2px; flex-shrink: 0; accent-color: ${this.colorOutbound};" />
          <label for="summary-accept-detours" style="flex: 1; cursor: pointer; margin: 0;">
            <div style="font-size: 15px; font-weight: 600; color: #1d1d1f; margin-bottom: 6px;font-family:${this.fontFamily};">
              Acceptez-vous de recevoir des demandes de passagers sur votre chemin ?
            </div>
            <div style="font-size: 13px; color: #6B6B6F; line-height: 1.5;font-family:${this.fontFamily};">
              Des personnes pourront vous demander de faire un léger détour pour les prendre en charge. <strong style="color: #1d1d1f;">Vous restez libre d'accepter ou de refuser chaque demande</strong>.
            </div>
          </label>
        </div>
        
        <!-- Budget temps (visible seulement si checkbox cochée) -->
        <div id="summary-detour-slider-section" style="padding-top: 18px; border-top: 1px solid rgba(10, 132, 255, 0.15);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <label style="font-size: 14px; font-weight: 600; color: ${textPrimary}; margin: 0;font-family:${this.fontFamily};">
              ⏱️ Budget temps pour les détours
            </label>
            <span id="summary-detour-time-display" style="font-size: 18px; font-weight: 700; color: ${this.colorOutbound}; min-width: 80px; text-align: right;font-family:${this.fontFamily};">5 min</span>
          </div>
          <input type="range" id="summary-detour-time-slider" min="5" max="20" value="5" step="5" 
            style="width: 100%; height: 6px; cursor: pointer; accent-color: ${this.colorOutbound}; background: linear-gradient(to right, ${this.colorOutbound} 0%, ${this.colorOutbound} 9.5%, #E5E5EA 9.5%, #E5E5EA 100%); border-radius: 3px; -webkit-appearance: none; appearance: none;" />
          <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 11px; color: #8E8E93; font-weight: 500;font-family:${this.fontFamily};">
            <span>5 min</span>
            <span>20 min</span>
          </div>
          <div style="margin-top: 10px; padding: 10px; background: rgba(52, 199, 89, 0.08); border-radius: 8px; font-size: 12px; color: #6B6B6F; line-height: 1.4;font-family:${this.fontFamily};">
            ✨ <strong style="color: #1d1d1f;">Budget intelligent :</strong> Temps total que vous acceptez d'ajouter à votre trajet pour tous les passagers. La zone verte sur la carte correspond à ce budget temps.
          </div>
        </div>
      </div>
      
      <!-- Impact CO2 (juste avant les coordonnées) -->
      <div id="summary-co2-impact" style="margin: 20px; padding: 16px; background: linear-gradient(135deg, rgba(52, 199, 89, 0.08) 0%, rgba(52, 199, 89, 0.02) 100%); border: 1px solid rgba(52, 199, 89, 0.2); border-radius: 12px;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L3 7v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V7l-9-5z" stroke="#34C759" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M12 8v8M8 12h8" stroke="#34C759" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <div style="flex: 1;">
            <div style="font-size: 13px; font-weight: 600; color: #34C759; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-family: ${this.fontFamily};">Impact environnemental</div>
            <div style="font-size: 15px; font-weight: 700; color: #1d1d1f; font-family: ${this.fontFamily};" id="summary-co2-value">~0 kg CO₂ évités</div>
            <div style="font-size: 12px; color: #6B6B6F; margin-top: 2px; font-family: ${this.fontFamily};" id="summary-co2-detail">par trajet partagé</div>
          </div>
        </div>
      </div>
      
      <!-- Coordonnées du conducteur (étape finale) -->
      <div style="margin: 20px; padding: 20px; background: linear-gradient(135deg, rgba(10, 132, 255, 0.05) 0%, rgba(10, 132, 255, 0.02) 100%); border-radius: 14px; border: 1px solid rgba(10, 132, 255, 0.15);">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="7" r="4" stroke="${this.colorOutbound}" stroke-width="2"/>
            <path d="M6 21v-2a4 4 0 014-4h4a4 4 0 014 4v2" stroke="${this.colorOutbound}" stroke-width="2"/>
          </svg>
          <h3 style="margin: 0; font-size: 17px; font-weight: 700; color: ${textPrimary}; font-family: ${this.fontFamily};">Vos coordonnées</h3>
        </div>
        <p style="margin: 0 0 16px 0; font-size: 13px; color: #6B6B6F; line-height: 1.5; font-family: ${this.fontFamily};">
          Pour vous contacter en cas de réservation et vous envoyer les détails par email avec le bouton WhatsApp.
        </p>
        
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <!-- Nom complet -->
          <div style="display: flex; align-items: center; gap: 12px; background: ${bgPrimary}; border: 1px solid ${inputBorder}; border-radius: 10px; padding: 12px 14px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink: 0; color: ${textSecondary};">
              <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/>
              <path d="M6 21v-2a4 4 0 014-4h4a4 4 0 014 4v2" stroke="currentColor" stroke-width="2"/>
            </svg>
            <input 
              id="driver-name" 
              type="text" 
              autocomplete="name" 
              placeholder="Votre nom complet" 
              style="flex: 1; border: none; background: transparent; outline: none; font-size: 15px; color: ${textPrimary}; font-family: ${this.fontFamily};" 
            />
          </div>
          
          <!-- Email -->
          <div style="display: flex; align-items: center; gap: 12px; background: ${bgPrimary}; border: 1px solid ${inputBorder}; border-radius: 10px; padding: 12px 14px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink: 0; color: ${textSecondary};">
              <rect x="2" y="4" width="20" height="16" rx="2" stroke="currentColor" stroke-width="2"/>
              <path d="M2 7l8.16 5.45a2 2 0 002.68 0L22 7" stroke="currentColor" stroke-width="2"/>
            </svg>
            <input 
              id="driver-email" 
              type="email" 
              autocomplete="email" 
              placeholder="Votre email" 
              style="flex: 1; border: none; background: transparent; outline: none; font-size: 15px; color: ${textPrimary}; font-family: ${this.fontFamily};" 
            />
          </div>
          
          <!-- Téléphone -->
          <div style="display: flex; align-items: center; gap: 12px; background: ${bgPrimary}; border: 1px solid ${inputBorder}; border-radius: 10px; padding: 12px 14px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink: 0; color: ${textSecondary};">
              <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" stroke="currentColor" stroke-width="2"/>
            </svg>
            <input 
              id="driver-phone" 
              type="tel" 
              autocomplete="tel" 
              placeholder="Téléphone (ex: 06 12 34 56 78)" 
              style="flex: 1; border: none; background: transparent; outline: none; font-size: 15px; color: ${textPrimary}; font-family: ${this.fontFamily};" 
            />
          </div>
        </div>
      </div>
      
      <!-- Bouton Valider -->
      <button id="validate-offer" class="btn-primary btn-validate-summary">Publier mon offre</button>
    </div>

    <!-- (loading/success views are injected into .card dynamically) -->
    
    </div>
  `;
}


  initMap() {
    const isDark = this.getAttribute('theme') === 'dark';
    const mapStyle = isDark 
      ? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
      : "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
    
    this.map = new maplibregl.Map({
      container: this.shadowRoot.getElementById("map"),
      style: mapStyle,
      center: [2.8089, 50.4264],
      zoom: 5,
      pitch: 0
    });
    this.map.addControl(new maplibregl.NavigationControl());
    
    // Animation d'entrée premium
    this.map.on('load', () => {
      this.map.easeTo({
        zoom: 6,
        pitch: 20,
        duration: 1500,
        easing: (t) => t * (2 - t) // easeOutQuad
      });
    });
    
    // Force le resize juste après l'init pour régler le bug d'affichage
    setTimeout(() => {
      this.map.resize();
    }, 100);
  }

  // --- Helpers d'affichage: cercle de rayon autour de la destination ---
  createCirclePolygon(center, radiusMeters, steps = 64) {
    if (!Array.isArray(center) || center.length !== 2) return null;
    const [lon0, lat0] = center;
    const coords = [];
    const Rlat = 111320; // mètres par degré de latitude
    const latRad = lat0 * Math.PI / 180;
    const Rlon = 111320 * Math.cos(latRad) || 111320; // évite NaN quand cos ~ 0
    const dLat = radiusMeters / Rlat;
    const dLon = radiusMeters / Rlon;
    for (let i = 0; i <= steps; i++) {
      const t = (i / steps) * 2 * Math.PI;
      const lat = lat0 + dLat * Math.sin(t);
      const lon = lon0 + dLon * Math.cos(t);
      coords.push([lon, lat]);
    }
    return {
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [coords] }
    };
  }

  updateDestinationRadius(radiusMeters = 5000) {
    try {
      if (!this.map || !this.stadiumCoords) return; // toujours centré sur le stade
      const data = this.createCirclePolygon(this.stadiumCoords, radiusMeters);
      if (!data) return;
      const srcId = 'destination-radius';
      const layerId = 'destination-radius-fill';
      const beforeId = this.map.getLayer(this.routeLayerId) ? this.routeLayerId : undefined;

      if (this.map.getSource(srcId)) {
        const src = this.map.getSource(srcId);
        if (src && src.setData) src.setData(data);
        // s'assurer que le layer existe encore
        if (!this.map.getLayer(layerId)) {
          const layerDef = {
            id: layerId,
            type: 'fill',
            source: srcId,
            paint: {
              'fill-color': '#1e8f2e',
              'fill-opacity': 0.08,
              'fill-outline-color': '#1e8f2e'
            }
          };
          if (beforeId) this.map.addLayer(layerDef, beforeId); else this.map.addLayer(layerDef);
        }
        return;
      }

      // créer source + layer
      this.map.addSource(srcId, { type: 'geojson', data });
      const layerDef = {
        id: layerId,
        type: 'fill',
        source: srcId,
        paint: {
          'fill-color': '#1e8f2e',
          'fill-opacity': 0.08,
          'fill-outline-color': '#1e8f2e'
        }
      };
      if (beforeId) this.map.addLayer(layerDef, beforeId); else this.map.addLayer(layerDef);
    } catch (e) {
      // si le style n'est pas encore prêt, réessaye bientôt
      setTimeout(() => { try { this.updateDestinationRadius(radiusMeters); } catch(_){} }, 300);
    }
  }

  // Haversine: distance en mètres entre deux [lon,lat]
  haversineMeters(a, b) {
    if (!a || !b) return NaN;
    const toRad = d => d * Math.PI / 180;
    const [lon1, lat1] = a; const [lon2, lat2] = b;
    const R = 6371000; // m
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const la1 = toRad(lat1), la2 = toRad(lat2);
    const h = Math.sin(dLat/2)**2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLon/2)**2;
    const c = 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
    return R * c;
  }
  
  /**
   * Calcule la distance minimale d'un point à un segment de ligne
   * @param {Array} point - [lon, lat] du point
   * @param {Array} segStart - [lon, lat] du début du segment
   * @param {Array} segEnd - [lon, lat] de la fin du segment
   * @returns {number} Distance en mètres
   */
  distanceToSegment(point, segStart, segEnd) {
    const [px, py] = point;
    const [x1, y1] = segStart;
    const [x2, y2] = segEnd;
    
    // Longueur du segment au carré (en degrés²)
    const segLengthSq = (x2 - x1) ** 2 + (y2 - y1) ** 2;
    
    if (segLengthSq === 0) {
      // Segment de longueur nulle, retourner distance au point
      return this.haversineMeters(point, segStart);
    }
    
    // Calculer la projection du point sur la ligne du segment
    // t représente la position sur le segment (0 = début, 1 = fin)
    let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / segLengthSq;
    
    // Limiter t à [0, 1] pour rester sur le segment
    t = Math.max(0, Math.min(1, t));
    
    // Point le plus proche sur le segment
    const closestPoint = [
      x1 + t * (x2 - x1),
      y1 + t * (y2 - y1)
    ];
    
    // Distance du point au point le plus proche sur le segment
    return this.haversineMeters(point, closestPoint);
  }
  
  /**
   * Vérifie si un point est à l'intérieur d'un polygone (ray casting algorithm)
   * @param {Array} point - [lon, lat]
   * @param {Array} polygon - Array de [lon, lat] représentant les sommets du polygone
   * @returns {boolean}
   */
  pointInPolygon(point, polygon) {
    const [x, y] = point;
    let inside = false;
    
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const [xi, yi] = polygon[i];
      const [xj, yj] = polygon[j];
      
      const intersect = ((yi > y) !== (yj > y)) && 
                       (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    
    return inside;
  }
  
  /**
   * Affiche un message simple à l'utilisateur
   * @param {string} message
   * @param {string} type - 'success', 'warning', 'error'
   */
  showToast(message, type = 'info') {
    // Pour l'instant, on utilise console.log et un système d'alerte simple
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Crée un toast si aucun système de notification DOM n'existe
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      padding: 15px 20px;
      background: ${type === 'error' ? '#ef4444' : type === 'warning' ? '#f59e0b' : '#10b981'};
      color: white;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 10000;
      font-family: ${this.fontFamily};
      font-size: 14px;
      max-width: 350px;
      opacity: 0;
      transition: opacity 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Fade in
    setTimeout(() => toast.style.opacity = '1', 10);
    
    // Fade out and remove
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }
  
  /**
   * Génère une grille de points échantillonnés dans les limites d'un polygone
   * @param {Object} polygon - Polygone GeoJSON
   * @param {number} gridSpacingKm - Espacement de la grille en km
   * @returns {Array} - Array de [lon, lat] dans le polygone
   */
  samplePointsInPolygon(polygon, gridSpacingKm = 0.5) {
    try {
      if (!polygon || !polygon.coordinates || !polygon.coordinates[0]) {
        return [];
      }
      
      const coords = polygon.coordinates[0];
      
      // Calculer les limites (bounding box)
      let minLon = Infinity, maxLon = -Infinity;
      let minLat = Infinity, maxLat = -Infinity;
      
      for (const [lon, lat] of coords) {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
      
      // Convertir espacement km en degrés (approximation)
      const latStep = gridSpacingKm / 111; // 1° lat ≈ 111km
      const avgLat = (minLat + maxLat) / 2;
      const lonStep = gridSpacingKm / (111 * Math.cos(avgLat * Math.PI / 180));
      
      const points = [];
      
      // Générer la grille
      for (let lat = minLat; lat <= maxLat; lat += latStep) {
        for (let lon = minLon; lon <= maxLon; lon += lonStep) {
          const point = [lon, lat];
          // Vérifier si le point est dans le polygone
          if (this.pointInPolygon(point, coords)) {
            points.push(point);
          }
        }
      }
      
      return points;
    } catch (e) {
      console.error('Error sampling points in polygon:', e);
      return [];
    }
  }
  
  /**
   * Calcule le temps de détour en minutes pour un point via OSRM
   * @param {Array} start - [lon, lat] départ
   * @param {Array} via - [lon, lat] point de rencontre
   * @param {Array} end - [lon, lat] arrivée
   * @returns {Promise<number|null>} - Temps de détour en minutes, ou null si erreur
   */
  async calculateDetourTimeOSRM(start, via, end) {
    try {
      // Route avec détour : start → via → end
      const detourUrl = `https://router.project-osrm.org/route/v1/driving/${start[0]},${start[1]};${via[0]},${via[1]};${end[0]},${end[1]}?overview=false`;
      const detourResp = await fetch(detourUrl);
      
      if (!detourResp.ok) return null;
      
      const detourData = await detourResp.json();
      if (detourData.code !== 'Ok' || !detourData.routes || !detourData.routes[0]) {
        return null;
      }
      
      const detourDuration = detourData.routes[0].duration / 60; // en minutes
      
      // Route directe : start → end
      const directUrl = `https://router.project-osrm.org/route/v1/driving/${start[0]},${start[1]};${end[0]},${end[1]}?overview=false`;
      const directResp = await fetch(directUrl);
      
      if (!directResp.ok) return null;
      
      const directData = await directResp.json();
      if (directData.code !== 'Ok' || !directData.routes || !directData.routes[0]) {
        return null;
      }
      
      const directDuration = directData.routes[0].duration / 60; // en minutes
      
      // Temps de détour = différence
      return detourDuration - directDuration;
      
    } catch (e) {
      console.error('Error calculating detour time:', e);
      return null;
    }
  }
  
  /**
   * Calcule l'intersection approximative entre deux polygones
  * Méthode simplifiée : garde les points du polygone 1 qui sont dans le polygone 2
   * @param {Object} polygon1 - Premier polygone GeoJSON
   * @param {Object} polygon2 - Deuxième polygone GeoJSON
   * @returns {Object|null} - Polygone GeoJSON de l'intersection, ou null
   */
  calculatePolygonIntersection(polygon1, polygon2) {
    try {
      if (!polygon1 || !polygon2 || !polygon1.coordinates || !polygon2.coordinates) {
        return null;
      }
      
      const coords1 = polygon1.coordinates[0];
      const coords2 = polygon2.coordinates[0];
      
      if (!coords1 || !coords2 || coords1.length < 3 || coords2.length < 3) {
        return null;
      }
      
      // Points d'intersection : points du polygone 1 dans le polygone 2 + points du polygone 2 dans le polygone 1
      const intersectionPoints = [];
      
      // Ajouter les points du polygone 1 qui sont dans le polygone 2
      for (const point of coords1) {
        if (this.pointInPolygon(point, coords2)) {
          intersectionPoints.push(point);
        }
      }
      
      // Ajouter les points du polygone 2 qui sont dans le polygone 1
      for (const point of coords2) {
        if (this.pointInPolygon(point, coords1)) {
          // Éviter les doublons
          const isDuplicate = intersectionPoints.some(p => 
            Math.abs(p[0] - point[0]) < 0.00001 && Math.abs(p[1] - point[1]) < 0.00001
          );
          if (!isDuplicate) {
            intersectionPoints.push(point);
          }
        }
      }
      
      // Besoin d'au moins 3 points pour un polygone
      if (intersectionPoints.length < 3) {
        return null;
      }
      
      // Trier les points par angle depuis le centre pour former un polygone valide
      const centerLon = intersectionPoints.reduce((sum, p) => sum + p[0], 0) / intersectionPoints.length;
      const centerLat = intersectionPoints.reduce((sum, p) => sum + p[1], 0) / intersectionPoints.length;
      
      intersectionPoints.sort((a, b) => {
        const angleA = Math.atan2(a[1] - centerLat, a[0] - centerLon);
        const angleB = Math.atan2(b[1] - centerLat, b[0] - centerLon);
        return angleA - angleB;
      });
      
      // Fermer le polygone
      intersectionPoints.push(intersectionPoints[0]);
      
      return {
        type: 'Polygon',
        coordinates: [intersectionPoints]
      };
      
    } catch (e) {
      console.error('Error calculating polygon intersection:', e);
      return null;
    }
  }
  
  /**
   * Calcule la zone cliquable étendue pour le point de rencontre
   * Simple : projette le point client sur la route, prend ±5km, crée buffer
   * @param {Object} bufferZone - Le buffer GeoJSON (non utilisé)
   * @param {Object} routeGeometry - La route GeoJSON {type: 'LineString', coordinates: [...]}
   * @param {Array} searchCenter - [lon, lat] du centre de recherche du client
   * @param {number} searchRadius - Rayon en mètres (non utilisé maintenant)
   * @returns {Object|null} - Polygon GeoJSON de la zone cliquable
   */
  calculateExtendedClickableZone(bufferZone, routeGeometry, searchCenter, searchRadius) {
    console.log('🔍 calculateExtendedClickableZone called with:', {
      hasBuffer: !!bufferZone,
      hasRoute: !!routeGeometry,
      searchCenter,
      searchRadius
    });
    
    try {
      // bufferZone EST déjà la geometry {type: 'Polygon', coordinates: [...]}
      if (!bufferZone || !bufferZone.coordinates || !routeGeometry || !searchCenter) {
        console.warn('Missing parameters for clickable zone calculation');
        return null;
      }
      
      const routeCoords = routeGeometry.coordinates;
      const bufferCoords = bufferZone.coordinates[0]; // Le contour du buffer existant
      
      console.log(`📊 Route: ${routeCoords.length} points, Buffer: ${bufferCoords.length} points`);
      
      // 1. Trouver le point sur la route le plus proche du searchCenter
      const projectedIdx = this.findNearestPointOnRoute(searchCenter, routeCoords);
      console.log(`📍 Projected point at index ${projectedIdx}`);
      
      // 2. Parcourir la route ±5km pour trouver les indices de début et fin
      const targetDistance = 5000; // 5km
      
      let startIdx = projectedIdx;
      let distBack = 0;
      for (let i = projectedIdx - 1; i >= 0; i--) {
        distBack += this.haversineMeters(routeCoords[i], routeCoords[i + 1]);
        if (distBack >= targetDistance) {
          startIdx = i;
          break;
        }
      }
      
      let endIdx = projectedIdx;
      let distForward = 0;
      for (let i = projectedIdx; i < routeCoords.length - 1; i++) {
        distForward += this.haversineMeters(routeCoords[i], routeCoords[i + 1]);
        if (distForward >= targetDistance) {
          endIdx = i;
          break;
        }
      }
      
      console.log(`📏 Route segment: indices ${startIdx} to ${endIdx} (${((distBack + distForward) / 1000).toFixed(1)}km total)`);
      
      // 3. Extraire la section de la route (10km total)
      const routeSegment = routeCoords.slice(startIdx, endIdx + 1);
      
      if (routeSegment.length < 2) {
        console.warn('⚠️ Route segment too short');
        return null;
      }
      
      // 4. Pour chaque point du buffer, vérifier s'il est proche d'un point du segment
      //    On garde les points du buffer qui sont à moins de (max_detour_km + 1km) d'un point du segment
      const maxBufferDist = ((this._currentOfferMaxDetour || 6) + 1) * 1000; // En mètres, +1km de marge
      const filteredBufferPoints = [];
      
      for (let i = 0; i < bufferCoords.length; i++) {
        const bufferPoint = bufferCoords[i];
        
        // Vérifier la distance minimale à n'importe quel point du segment
        let minDistToSegment = Infinity;
        for (let j = 0; j < routeSegment.length; j++) {
          const dist = this.haversineMeters(bufferPoint, routeSegment[j]);
          if (dist < minDistToSegment) {
            minDistToSegment = dist;
          }
        }
        
        // Si ce point du buffer est proche du segment, on le garde
        if (minDistToSegment <= maxBufferDist) {
          filteredBufferPoints.push(bufferPoint);
        }
      }
      
      console.log(`🔪 Filtered buffer: ${filteredBufferPoints.length} points out of ${bufferCoords.length}`);
      
      if (filteredBufferPoints.length < 3) {
        console.warn('⚠️ Not enough buffer points after filtering');
        return null;
      }
      
      // 5. Fermer le polygone
      if (filteredBufferPoints[0] !== filteredBufferPoints[filteredBufferPoints.length - 1]) {
        filteredBufferPoints.push(filteredBufferPoints[0]);
      }
      
      console.log('✅ Clickable zone created:', filteredBufferPoints.length, 'points');
      
      return {
        type: 'Polygon',
        coordinates: [filteredBufferPoints]
      };
      
    } catch (e) {
      console.error('❌ Error calculating extended clickable zone:', e);
      return null;
    }
  }
  
  /**
   * Trouve l'index du point le plus proche sur la route
   * @param {Array} point - [lon, lat]
   * @param {Array} routeCoords - Array de [lon, lat]
   * @returns {number} - Index du point le plus proche
   */
  findNearestPointOnRoute(point, routeCoords) {
    let minDist = Infinity;
    let minIdx = 0;
    
    for (let i = 0; i < routeCoords.length; i++) {
      const dist = this.haversineMeters(point, routeCoords[i]);
      if (dist < minDist) {
        minDist = dist;
        minIdx = i;
      }
    }
    
    return minIdx;
  }
  
  /**
   * Crée un buffer (polygone GeoJSON) autour d'une LineString.
   * Méthode améliorée : échantillonnage avec lissage des angles et filtrage des virages serrés.
   * @param {Array} lineCoords - Array de [lon, lat] représentant la LineString
   * @param {number} bufferKm - Distance du buffer en kilomètres
   * @returns {Object} - GeoJSON Polygon représentant la zone tampon
   */
  createBufferAroundRoute(lineCoords, bufferKm) {
    if (!Array.isArray(lineCoords) || lineCoords.length < 2) {
      console.warn('createBufferAroundRoute: invalid lineCoords');
      return null;
    }

    // Si JSTS est disponible, l'utiliser pour un buffer propre et rapide
    if (window.jsts) {
      try {
        const reader = new jsts.io.GeoJSONReader();
        const writer = new jsts.io.GeoJSONWriter();
        
        // Convertir en GeoJSON puis en géométrie JSTS
        const lineGeoJSON = { type: 'LineString', coordinates: lineCoords };
        const jstsGeom = reader.read(lineGeoJSON);
        
        // Créer le buffer (distance en degrés approximatifs)
        const bufferDistDeg = bufferKm / 111;
        const buffered = jstsGeom.buffer(bufferDistDeg);
        
        // Reconvertir en GeoJSON
        const result = writer.write(buffered);
        console.log(`Buffer créé avec JSTS (rapide et propre comme QGIS)`);
        return result;
      } catch (error) {
        console.warn('JSTS buffer failed, falling back to manual method:', error);
      }
    }

    // Fallback : méthode manuelle
    const bufferMeters = bufferKm * 1000;
    const offsetDeg = (bufferMeters / 1000) / 111;
    
    // Calculer les distances cumulées le long de la route
    const distances = [0];
    for (let i = 1; i < lineCoords.length; i++) {
      const [lon1, lat1] = lineCoords[i - 1];
      const [lon2, lat2] = lineCoords[i];
      const dLon = (lon2 - lon1) * Math.cos((lat1 + lat2) / 2 * Math.PI / 180);
      const dLat = lat2 - lat1;
      const dist = Math.sqrt(dLon * dLon + dLat * dLat) * 111000; // en mètres
      distances.push(distances[i - 1] + dist);
    }
    const totalDistance = distances[distances.length - 1];
    
    console.log(`Route totale: ${(totalDistance/1000).toFixed(1)}km - Buffer avec cônes de 5km`);
    
    // Simplifier légèrement pour les performances, mais garder beaucoup de détails
    const simplificationFactor = Math.max(1, Math.floor(lineCoords.length / 500));
    const simplifiedCoords = [];
    const simplifiedDistances = [];
    
    for (let i = 0; i < lineCoords.length; i += simplificationFactor) {
      simplifiedCoords.push(lineCoords[i]);
      simplifiedDistances.push(distances[i]);
    }
    
    // Toujours inclure le dernier point
    if (simplifiedCoords[simplifiedCoords.length - 1] !== lineCoords[lineCoords.length - 1]) {
      simplifiedCoords.push(lineCoords[lineCoords.length - 1]);
      simplifiedDistances.push(distances[distances.length - 1]);
    }
    
    // Pas de filtrage d'angles - on garde tous les points pour suivre parfaitement la route
    const filteredCoords = simplifiedCoords;
    const filteredDistances = simplifiedDistances;
    
    if (filteredCoords.length < 2) {
      return null;
    }
    
    const leftSide = [];
    const rightSide = [];
    
    // Créer les côtés avec un buffer en forme de cône aux extrémités
    for (let i = 0; i < filteredCoords.length; i++) {
      const [lon, lat] = filteredCoords[i];
      const distFromStart = filteredDistances[i];
      const distFromEnd = totalDistance - distFromStart;
      
      // Calculer le facteur d'élargissement en cône
      let widthFactor = 1.0;
      const coneDistance = 5000; // 5km de transition
      
      if (distFromStart < coneDistance) {
        // Progression de 0 à 1 sur les 5 premiers km
        widthFactor = distFromStart / coneDistance;
      } else if (distFromEnd < coneDistance) {
        // Régression de 1 à 0 sur les 5 derniers km
        widthFactor = distFromEnd / coneDistance;
      }
      
      const effectiveOffset = offsetDeg * widthFactor;
      
      // Calculer la direction avec lissage
      let dx, dy;
      
      if (filteredCoords.length <= 2) {
        const [lon2, lat2] = filteredCoords[filteredCoords.length - 1];
        dx = lon2 - lon;
        dy = lat2 - lat;
      } else if (i < 3) {
        // Début: regarder loin devant
        const lookAhead = Math.min(5, filteredCoords.length - 1);
        const [lonAhead, latAhead] = filteredCoords[lookAhead];
        dx = lonAhead - lon;
        dy = latAhead - lat;
      } else if (i > filteredCoords.length - 4) {
        // Fin: regarder loin derrière
        const lookBehind = Math.max(0, filteredCoords.length - 6);
        const [lonBehind, latBehind] = filteredCoords[lookBehind];
        dx = lon - lonBehind;
        dy = lat - latBehind;
      } else {
        // Milieu: moyenne sur une large fenêtre
        const windowSize = 3;
        const startIdx = Math.max(0, i - windowSize);
        const endIdx = Math.min(filteredCoords.length - 1, i + windowSize);
        
        const [startLon, startLat] = filteredCoords[startIdx];
        const [endLon, endLat] = filteredCoords[endIdx];
        
        dx = endLon - startLon;
        dy = endLat - startLat;
      }
      
      // Normaliser
      const length = Math.sqrt(dx * dx + dy * dy) || 0.001;
      dx /= length;
      dy /= length;
      
      // Perpendiculaire (rotation de 90°)
      const perpX = -dy;
      const perpY = dx;
      
      leftSide.push([lon + perpX * effectiveOffset, lat + perpY * effectiveOffset]);
      rightSide.push([lon - perpX * effectiveOffset, lat - perpY * effectiveOffset]);
    }
    
    // Assembler le polygone: gauche + droite inversée
    rightSide.reverse();
    const coords = [...leftSide, ...rightSide, leftSide[0]];
    
    return {
      type: 'Polygon',
      coordinates: [coords]
    };
  }

  /**
   * Créer un buffer autour d'une route en fonction du temps de détour disponible
   * @param {Array} routeCoords - Coordonnées de la route [[lon, lat], ...]
   * @param {number} maxDetourTimeMin - Temps de détour maximum en minutes
   * @returns {Object|null} - GeoJSON Polygon du buffer
   */
  createRouteBuffer(routeCoords, maxDetourTimeMin) {
    if (!Array.isArray(routeCoords) || routeCoords.length < 2) {
      console.warn('createRouteBuffer: invalid routeCoords');
      return null;
    }
    
    // Estimer une vitesse moyenne (50 km/h en zone urbaine/périurbaine)
    const avgSpeedKmH = 50;
    
    // Calculer le rayon du buffer en km
    // On divise par 2 car le détour se fait aller-retour depuis la route
    // On applique un facteur de sécurité de 0.3 pour être conservateur
    const bufferKm = (avgSpeedKmH * (maxDetourTimeMin / 60) * 0.5 * 0.3);
    
    console.log(`Buffer route récurrent: ${maxDetourTimeMin} min → ${bufferKm.toFixed(2)} km de rayon`);
    
    // Utiliser la méthode existante de création de buffer
    return this.createBufferAroundRoute(routeCoords, bufferKm);
  }

  /**
   * Version simple de createBufferAroundRoute sans exclusion des extrémités
   * Utilisée comme fallback
   */
  createBufferAroundRouteSimple(lineCoords, bufferKm) {
    if (!Array.isArray(lineCoords) || lineCoords.length < 2) {
      return null;
    }

    const bufferMeters = bufferKm * 1000;
    const offsetDeg = (bufferMeters / 1000) / 111;
    
    const totalPoints = lineCoords.length;
    const targetSamples = Math.min(120, Math.max(80, Math.floor(totalPoints / 3)));
    const step = Math.max(1, Math.floor(totalPoints / targetSamples));
    const sampledPoints = [];
    
    for (let i = 0; i < totalPoints; i += step) {
      sampledPoints.push(lineCoords[i]);
    }
    
    if (sampledPoints[sampledPoints.length - 1] !== lineCoords[totalPoints - 1]) {
      sampledPoints.push(lineCoords[totalPoints - 1]);
    }
    
    const leftSide = [];
    const rightSide = [];
    
    for (let i = 0; i < sampledPoints.length; i++) {
      const [lon, lat] = sampledPoints[i];
      
      let dx, dy;
      
      if (i === 0 && sampledPoints.length > 1) {
        const [lon2, lat2] = sampledPoints[1];
        dx = lon2 - lon;
        dy = lat2 - lat;
      } else if (i === sampledPoints.length - 1 && sampledPoints.length > 1) {
        const [lon1, lat1] = sampledPoints[i - 1];
        dx = lon - lon1;
        dy = lat - lat1;
      } else if (sampledPoints.length > 2) {
        const windowSize = Math.min(2, Math.floor(sampledPoints.length / 10));
        const startIdx = Math.max(0, i - windowSize);
        const endIdx = Math.min(sampledPoints.length - 1, i + windowSize);
        
        const [startLon, startLat] = sampledPoints[startIdx];
        const [endLon, endLat] = sampledPoints[endIdx];
        
        dx = endLon - startLon;
        dy = endLat - startLat;
      } else {
        dx = 0;
        dy = 0.001;
      }
      
      const length = Math.sqrt(dx * dx + dy * dy) || 0.001;
      dx /= length;
      dy /= length;
      
      const perpX = -dy;
      const perpY = dx;
      
      leftSide.push([lon + perpX * offsetDeg, lat + perpY * offsetDeg]);
      rightSide.push([lon - perpX * offsetDeg, lat - perpY * offsetDeg]);
    }
    
    const smoothSide = (side) => {
      if (side.length < 3) return side;
      const smoothed = [side[0]];
      
      for (let i = 1; i < side.length - 1; i++) {
        const prev = side[i - 1];
        const curr = side[i];
        const next = side[i + 1];
        
        const smoothLon = 0.5 * curr[0] + 0.25 * prev[0] + 0.25 * next[0];
        const smoothLat = 0.5 * curr[1] + 0.25 * prev[1] + 0.25 * next[1];
        
        smoothed.push([smoothLon, smoothLat]);
      }
      
      smoothed.push(side[side.length - 1]);
      return smoothed;
    };
    
    const smoothedLeft = smoothSide(leftSide);
    const smoothedRight = smoothSide(rightSide);
    
    smoothedRight.reverse();
    const coords = [...smoothedLeft, ...smoothedRight, smoothedLeft[0]];
    
    return {
      type: 'Polygon',
      coordinates: [coords]
    };
  }

  /**
   * Calcule l'enveloppe convexe (convex hull) d'un ensemble de points
   * Utilise l'algorithme de Graham scan
   * NOTE: Cette fonction n'est plus utilisée pour les buffers mais conservée pour compatibilité
   * @param {Array} points - Array de [lon, lat]
   * @returns {Array} - Points de l'enveloppe convexe
   */
  convexHull(points) {
    if (!points || points.length < 3) return points;
    
    // Trier les points par x, puis par y
    const sorted = [...points].sort((a, b) => a[0] === b[0] ? a[1] - b[1] : a[0] - b[0]);
    
    // Fonction pour calculer le produit vectoriel
    const cross = (o, a, b) => {
      return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    };
    
    // Construire la partie inférieure
    const lower = [];
    for (let i = 0; i < sorted.length; i++) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], sorted[i]) <= 0) {
        lower.pop();
      }
      lower.push(sorted[i]);
    }
    
    // Construire la partie supérieure
    const upper = [];
    for (let i = sorted.length - 1; i >= 0; i--) {
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], sorted[i]) <= 0) {
        upper.pop();
      }
      upper.push(sorted[i]);
    }
    
    // Retirer les derniers points car ils sont dupliqués
    lower.pop();
    upper.pop();
    
    return lower.concat(upper);
  }

  // Met à jour la couleur du disque et affiche une popup d'avertissement si la destination est hors rayon
  checkDestinationProximity(radiusMeters = 5000) {
    try {
      if (!this.map || !this.stadiumCoords || !this.endCoords) return;
      const layerId = 'destination-radius-fill';
      // s'assurer que la source/layer existent (créés au besoin)
      this.updateDestinationRadius(radiusMeters);
      const dist = this.haversineMeters(this.stadiumCoords, this.endCoords);
      const isOutside = Number.isFinite(dist) && dist > radiusMeters;
      // Couleur: vert si OK, rouge si hors rayon
      const fillColor = isOutside ? '#e53935' : '#1e8f2e';
      const outlineColor = fillColor;
      if (this.map.getLayer(layerId)) {
        this.map.setPaintProperty(layerId, 'fill-color', fillColor);
        this.map.setPaintProperty(layerId, 'fill-outline-color', outlineColor);
      }

      // Popup d'avertissement près du marqueur destination
      if (isOutside) {
        const msg = "Attention: votre adresse de destination semble trop éloignée du lieu de la prochaine rencontre !";
        if (!this.destWarningPopup) {
          this.destWarningPopup = new maplibregl.Popup({ closeButton: true, closeOnClick: false, maxWidth: '260px' })
            .setLngLat(this.endCoords)
            .setHTML(`<div style="font-family:${this.fontFamily};font-size:13px;color:#333;line-height:1.3">
              ${msg}
            </div>`)
            .addTo(this.map);
        } else {
          this.destWarningPopup.setLngLat(this.endCoords).setHTML(`<div style="font-family:${this.fontFamily};font-size:13px;color:#333;line-height:1.3">${msg}</div>`);
          if (!this.destWarningPopup.isOpen?.()) this.destWarningPopup.addTo(this.map);
        }
      } else {
        if (this.destWarningPopup) { try { this.destWarningPopup.remove(); } catch(_){} this.destWarningPopup = null; }
      }
    } catch (_) { /* ignore */ }
  }

  initRSETransportCalendar() {
    const container = this.shadowRoot.getElementById('rse-transport-calendar');
    console.log('🔧 initRSETransportCalendar appelée, container:', container, 'isRseMode:', this.isRseMode());
    
    if (!container) {
      console.log('❌ Container RSE non trouvé');
      return;
    }

    // Modes de transport avec leurs emojis (ordre de rotation)
    this.transportModes = [
      { id: 'car', emoji: '🚗', label: 'Voiture solo' },
      { id: 'bus', emoji: '🚌', label: 'Transports en commun' },
      { id: 'carpool', emoji: '🚗👥', label: 'Covoiturage' },
      { id: 'bike', emoji: '🚴', label: 'Vélo' },
      { id: 'train', emoji: '🚆', label: 'Train' },
      { id: 'telework', emoji: '🏠', label: 'Télétravail' },
      { id: 'walk', emoji: '🚶', label: 'Marche' },
      { id: 'off', emoji: '🌴', label: 'Ne travaille pas' }
    ];

    // Jours de la semaine
    // Jours de la semaine
    const weekDays = [
      { id: 'monday', label: 'Lun' },
      { id: 'tuesday', label: 'Mar' },
      { id: 'wednesday', label: 'Mer' },
      { id: 'thursday', label: 'Jeu' },
      { id: 'friday', label: 'Ven' },
      { id: 'saturday', label: 'Sam' },
      { id: 'sunday', label: 'Dim' }
    ];

    // Générer la grille: jours en haut, boutons emoji en dessous
    const html = `
      <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; padding: 8px 0;">
        ${weekDays.map((day, index) => {
          // Par défaut: samedi et dimanche = palmier (index 7), sinon voiture (index 0)
          const defaultModeIndex = (day.id === 'saturday' || day.id === 'sunday') ? 7 : 0;
          const defaultMode = this.transportModes[defaultModeIndex];
          
          return `
          <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
            <div style="font-size: 11px; font-weight: 600; color: #6b7280; text-align: center;">
              ${day.label}
            </div>
            <button 
              class="rse-day-transport-btn" 
              data-day="${day.id}"
              style="
                background: white;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                width: 48px;
                height: 48px;
                font-size: 22px;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                justify-content: center;
              "
              title="${defaultMode.label}"
              onclick="this.getRootNode().host.cycleTransportMode('${day.id}', this)"
            >
              ${defaultMode.emoji}
            </button>
          </div>
        `;
        }).join('')}
      </div>
    `;

    container.innerHTML = html;

    // Initialiser le stockage: samedi/dimanche = palmier, autres = voiture
    if (!this.rseTransportData) {
      this.rseTransportData = {};
      weekDays.forEach(day => {
        this.rseTransportData[day.id] = (day.id === 'saturday' || day.id === 'sunday') ? 7 : 0;
      });
    }
  }

  cycleTransportMode(dayId, button) {
    // Obtenir l'index actuel
    const currentIndex = this.rseTransportData[dayId] || 0;
    
    // Passer au mode suivant (avec boucle)
    const nextIndex = (currentIndex + 1) % this.transportModes.length;
    
    // Mettre à jour le stockage
    this.rseTransportData[dayId] = nextIndex;
    
    // Mettre à jour l'affichage
    const mode = this.transportModes[nextIndex];
    button.textContent = mode.emoji;
    button.title = mode.label;
    
    // Animation de clic
    button.style.transform = 'scale(0.9)';
    setTimeout(() => {
      button.style.transform = 'scale(1)';
    }, 100);

    console.log(`🚗 ${dayId}: ${mode.label} (${mode.emoji})`);
  }

  // Calcule les émissions CO2 pour chaque jour selon le mode de transport
  calculateRSECO2Emissions() {
    if (!this.routeAlternatives || !this.routeAlternatives[0]) {
      console.warn('calculateRSECO2Emissions: pas de distance calculée');
      return {};
    }

    // Distance en km (aller simple)
    const distanceKm = this.routeAlternatives[0].distance / 1000;
    
    // Facteurs d'émission CO2 en kg/km pour un ALLER-RETOUR (donc x2)
    // Sources : ADEME, Base Carbone
    const emissionFactors = {
      0: 0.218 * 2,  // Voiture solo (essence) : ~0.218 kg CO2/km × 2
      1: 0.050 * 2,  // Transports en commun : ~0.050 kg CO2/km × 2 (moyenne bus/métro/tram)
      2: 0.109 * 2,  // Covoiturage (2 pers) : ~0.109 kg CO2/km × 2
      3: 0,          // Vélo : 0 kg CO2/km
      4: 0.0029 * 2, // Train : ~0.0029 kg CO2/km × 2
      5: 0,          // Télétravail : 0 kg CO2/km
      6: 0,          // Marche : 0 kg CO2/km
      7: 0           // Jour off : 0 kg CO2/km
    };

    const emissions = {};
    const weekDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    
    weekDays.forEach(dayId => {
      const modeIndex = this.rseTransportData[dayId] || 0;
      const factor = emissionFactors[modeIndex] || 0;
      // Calculer les émissions pour ce jour (aller-retour = distance × 2)
      emissions[dayId] = parseFloat((distanceKm * 2 * factor).toFixed(2));
    });

    return emissions;
  }

  // Vérifie si l'utilisateur vient en voiture au moins un jour
  hasCarDays() {
    const weekDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    return weekDays.some(dayId => {
      const modeIndex = this.rseTransportData[dayId] || 0;
      return modeIndex === 0 || modeIndex === 2; // 0 = voiture solo, 2 = covoiturage
    });
  }

  // Génère le récapitulatif RSE dans trip-summary
  renderRSESummary() {
    const tripSummaryEl = this.shadowRoot.getElementById('trip-summary');
    if (!tripSummaryEl) return;

    const isDark = this.theme === 'dark';
    const textPrimary = isDark ? '#ffffff' : '#1d1d1f';
    const textSecondary = isDark ? '#a0a0a0' : '#8e8e93';

    // Calculer les émissions CO2
    const emissions = this.calculateRSECO2Emissions();
    
    // Récupérer la distance
    const distanceKm = this.routeAlternatives && this.routeAlternatives[0] 
      ? (this.routeAlternatives[0].distance / 1000).toFixed(0)
      : '0';

    const weekDays = [
      { id: 'monday', label: 'Lun' },
      { id: 'tuesday', label: 'Mar' },
      { id: 'wednesday', label: 'Mer' },
      { id: 'thursday', label: 'Jeu' },
      { id: 'friday', label: 'Ven' },
      { id: 'saturday', label: 'Sam' },
      { id: 'sunday', label: 'Dim' }
    ];

    // Calculer le total hebdomadaire
    const totalWeeklyCO2 = Object.values(emissions).reduce((sum, val) => sum + parseFloat(val || 0), 0).toFixed(2);

    const daysHTML = weekDays.map(day => {
      const modeIndex = this.rseTransportData[day.id] || 0;
      const mode = this.transportModes[modeIndex];
      const co2 = emissions[day.id] || '0.00';
      const co2Number = parseFloat(co2);
      
      // Couleur selon les émissions
      let co2Color = '#10b981'; // Vert par défaut
      if (co2Number > 10) co2Color = '#ef4444'; // Rouge si > 10 kg
      else if (co2Number > 5) co2Color = '#f59e0b'; // Orange si > 5 kg

      return `
        <div style="
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          padding: 12px;
          background: ${isDark ? '#2a2a2a' : '#f9fafb'};
          border: 2px solid ${isDark ? '#404040' : '#e5e7eb'};
          border-radius: 12px;
          transition: all 0.2s ease;
        ">
          <div style="
            font-size: 12px;
            font-weight: 700;
            color: ${textSecondary};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-family: ${this.fontFamily};
          ">
            ${day.label}
          </div>
          <div style="
            font-size: 32px;
            line-height: 1;
          ">
            ${mode.emoji}
          </div>
          <div style="
            font-size: 11px;
            color: ${textSecondary};
            text-align: center;
            font-family: ${this.fontFamily};
          ">
            ${mode.label}
          </div>
          <div style="
            font-size: 18px;
            font-weight: 900;
            color: ${co2Color};
            margin-top: 4px;
            font-family: ${this.fontFamily};
          ">
            ${co2} kg
          </div>
          <div style="
            font-size: 10px;
            color: ${textSecondary};
            font-family: ${this.fontFamily};
          ">
            CO₂
          </div>
        </div>
      `;
    }).join('');

    tripSummaryEl.innerHTML = `
      <div style="padding: 24px;">
        <div style="text-align: center; margin-bottom: 24px;">
          <div style="
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 64px;
            height: 64px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border-radius: 50%;
            margin-bottom: 16px;
          ">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2v20M5 12h14" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
              <circle cx="12" cy="7" r="2" fill="#fff"/>
              <circle cx="12" cy="17" r="2" fill="#fff"/>
            </svg>
          </div>
          <h2 style="
            margin: 0 0 8px 0;
            font-size: 28px;
            font-weight: 900;
            color: ${textPrimary};
            font-family: ${this.fontFamily};
          ">
            Récapitulatif RSE
          </h2>
          <p style="
            margin: 0;
            font-size: 15px;
            color: ${textSecondary};
            font-family: ${this.fontFamily};
          ">
            Distance domicile-travail : <strong>${distanceKm} km</strong> (aller simple)
          </p>
        </div>

        <div style="
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
          gap: 12px;
          margin-bottom: 24px;
        ">
          ${daysHTML}
        </div>

        <div style="
          padding: 20px;
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          border-radius: 16px;
          text-align: center;
          box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        ">
          <div style="
            font-size: 13px;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            font-family: ${this.fontFamily};
          ">
            Total hebdomadaire
          </div>
          <div style="
            font-size: 42px;
            font-weight: 900;
            color: white;
            margin-bottom: 4px;
            font-family: ${this.fontFamily};
          ">
            ${totalWeeklyCO2} kg
          </div>
          <div style="
            font-size: 14px;
            color: rgba(255, 255, 255, 0.85);
            font-family: ${this.fontFamily};
          ">
            d'émissions CO₂
          </div>
        </div>

        <div style="
          margin-top: 24px;
          padding: 16px;
          background: ${isDark ? '#2a2a2a' : '#f0f9ff'};
          border: 1px solid ${isDark ? '#404040' : '#bae6fd'};
          border-radius: 12px;
        ">
          <div style="
            display: flex;
            align-items: start;
            gap: 12px;
          ">
            <div style="
              font-size: 24px;
              line-height: 1;
            ">
              💡
            </div>
            <div style="
              flex: 1;
              font-size: 13px;
              color: ${textSecondary};
              line-height: 1.5;
              font-family: ${this.fontFamily};
            ">
              <strong style="color: ${textPrimary};">Astuce :</strong> 
              En privilégiant les transports en commun, le vélo ou le covoiturage, 
              vous pouvez réduire significativement votre empreinte carbone.
            </div>
          </div>
        </div>

        ${this.hasCarDays() ? `
          <div style="
            margin-top: 24px;
            padding: 20px;
            background: ${this.colorReturn};
            border-radius: 16px;
            box-shadow: 0 4px 12px ${this.colorReturn}33;
          ">
            <label style="
              display: flex;
              align-items: center;
              gap: 16px;
              cursor: pointer;
            ">
              <input 
                type="checkbox" 
                id="rse-offer-carpool-checkbox" 
                style="
                  width: 24px;
                  height: 24px;
                  cursor: pointer;
                  accent-color: white;
                "
              >
              <div style="flex: 1;">
                <div style="
                  font-size: 16px;
                  font-weight: 700;
                  color: white;
                  margin-bottom: 4px;
                  font-family: ${this.fontFamily};
                ">
                  🤝 Accepter les propositions de covoiturage
                </div>
                <div style="
                  font-size: 13px;
                  color: rgba(255, 255, 255, 0.9);
                  font-family: ${this.fontFamily};
                ">
                  Vous venez en voiture ? Nous vous préviendrons par email si des collègues peuvent covoiturer avec vous sur votre trajet.
                </div>
              </div>
            </label>
          </div>
          
          <!-- Section détails covoiturage (cachée par défaut) -->
          <div id="rse-carpool-details" style="display: none; margin-top: 20px;">
            <!-- Carte pour visualiser le trajet -->
            <div style="
              background: ${isDark ? '#1a1a1a' : '#ffffff'};
              border: 2px solid ${isDark ? '#404040' : '#e5e7eb'};
              border-radius: 12px;
              padding: 16px;
              margin-bottom: 16px;
            ">
              <h4 style="
                margin: 0 0 12px 0;
                font-size: 16px;
                font-weight: 700;
                color: ${textPrimary};
                font-family: ${this.fontFamily};
              ">
                🗺️ Votre trajet
              </h4>
              <div id="rse-map-container" style="
                width: 100%;
                height: 300px;
                border-radius: 8px;
                overflow: hidden;
              "></div>
            </div>
            
            <!-- Contrôle du temps de détour acceptable -->
            <div style="
              background: ${isDark ? '#1a1a1a' : '#ffffff'};
              border: 2px solid ${isDark ? '#404040' : '#e5e7eb'};
              border-radius: 12px;
              padding: 20px;
            ">
              <h4 style="
                margin: 0 0 12px 0;
                font-size: 16px;
                font-weight: 700;
                color: ${textPrimary};
                font-family: ${this.fontFamily};
              ">
                ⏱️ Temps de détour acceptable
              </h4>
              <p style="
                margin: 0 0 16px 0;
                font-size: 14px;
                color: ${textSecondary};
                font-family: ${this.fontFamily};
              ">
                Combien de temps de détour êtes-vous prêt(e) à accepter pour récupérer un covoitureur ?
              </p>
              
              <div style="margin-bottom: 16px;">
                <label style="
                  display: flex;
                  align-items: center;
                  gap: 12px;
                  cursor: pointer;
                  padding: 12px;
                  background: ${isDark ? '#2a2a2a' : '#f9fafb'};
                  border-radius: 8px;
                  transition: background 0.2s ease;
                "
                onmouseover="this.style.background='${isDark ? '#333' : '#f3f4f6'}'"
                onmouseout="this.style.background='${isDark ? '#2a2a2a' : '#f9fafb'}'">
                  <input type="radio" name="rse-detour-time" value="5" checked
                    style="width: 20px; height: 20px; cursor: pointer; accent-color: ${this.colorReturn};">
                  <span style="font-size: 15px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily};">
                    5 minutes maximum
                  </span>
                </label>
              </div>
              
              <div style="margin-bottom: 16px;">
                <label style="
                  display: flex;
                  align-items: center;
                  gap: 12px;
                  cursor: pointer;
                  padding: 12px;
                  background: ${isDark ? '#2a2a2a' : '#f9fafb'};
                  border-radius: 8px;
                  transition: background 0.2s ease;
                "
                onmouseover="this.style.background='${isDark ? '#333' : '#f3f4f6'}'"
                onmouseout="this.style.background='${isDark ? '#2a2a2a' : '#f9fafb'}'">
                  <input type="radio" name="rse-detour-time" value="10"
                    style="width: 20px; height: 20px; cursor: pointer; accent-color: ${this.colorReturn};">
                  <span style="font-size: 15px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily};">
                    10 minutes maximum
                  </span>
                </label>
              </div>
              
              <div>
                <label style="
                  display: flex;
                  align-items: center;
                  gap: 12px;
                  cursor: pointer;
                  padding: 12px;
                  background: ${isDark ? '#2a2a2a' : '#f9fafb'};
                  border-radius: 8px;
                  transition: background 0.2s ease;
                "
                onmouseover="this.style.background='${isDark ? '#333' : '#f3f4f6'}'"
                onmouseout="this.style.background='${isDark ? '#2a2a2a' : '#f9fafb'}'">
                  <input type="radio" name="rse-detour-time" value="15"
                    style="width: 20px; height: 20px; cursor: pointer; accent-color: ${this.colorReturn};">
                  <span style="font-size: 15px; font-weight: 600; color: ${textPrimary}; font-family: ${this.fontFamily};">
                    15 minutes maximum
                  </span>
                </label>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Champs de saisie utilisateur -->
        <div style="
          margin-top: 32px;
          padding: 24px;
          background: ${isDark ? '#1a1a1a' : '#ffffff'};
          border: 2px solid ${isDark ? '#404040' : '#e5e7eb'};
          border-radius: 16px;
        ">
          <h3 style="
            margin: 0 0 20px 0;
            font-size: 18px;
            font-weight: 700;
            color: ${textPrimary};
            font-family: ${this.fontFamily};
          ">
            👤 Vos informations
          </h3>

          <div style="margin-bottom: 16px;">
            <label style="
              display: block;
              font-size: 14px;
              font-weight: 600;
              color: ${textSecondary};
              margin-bottom: 8px;
              font-family: ${this.fontFamily};
            ">
              Nom et Prénom *
            </label>
            <input 
              type="text" 
              id="rse-user-name" 
              placeholder="Jean Dupont" 
              required
              style="
                width: 100%;
                padding: 12px 16px;
                font-size: 15px;
                border: 2px solid ${isDark ? '#404040' : '#d1d5db'};
                border-radius: 10px;
                background: ${isDark ? '#2a2a2a' : 'white'};
                color: ${textPrimary};
                font-family: ${this.fontFamily};
                transition: border-color 0.2s ease;
              "
              onfocus="this.style.borderColor='${this.accentColor}'"
              onblur="this.style.borderColor='${isDark ? '#404040' : '#d1d5db'}'"
            >
          </div>

          <div style="margin-bottom: 16px;">
            <label style="
              display: block;
              font-size: 14px;
              font-weight: 600;
              color: ${textSecondary};
              margin-bottom: 8px;
              font-family: ${this.fontFamily};
            ">
              Adresse email *
            </label>
            <input 
              type="email" 
              id="rse-user-email" 
              placeholder="jean.dupont@example.com" 
              required
              style="
                width: 100%;
                padding: 12px 16px;
                font-size: 15px;
                border: 2px solid ${isDark ? '#404040' : '#d1d5db'};
                border-radius: 10px;
                background: ${isDark ? '#2a2a2a' : 'white'};
                color: ${textPrimary};
                font-family: ${this.fontFamily};
                transition: border-color 0.2s ease;
              "
              onfocus="this.style.borderColor='${this.accentColor}'"
              onblur="this.style.borderColor='${isDark ? '#404040' : '#d1d5db'}'"
            >
          </div>

          <div style="margin-bottom: 0;">
            <label style="
              display: block;
              font-size: 14px;
              font-weight: 600;
              color: ${textSecondary};
              margin-bottom: 8px;
              font-family: ${this.fontFamily};
            ">
              Téléphone *
            </label>
            <input 
              type="tel" 
              id="rse-user-phone" 
              placeholder="06 12 34 56 78" 
              required
              style="
                width: 100%;
                padding: 12px 16px;
                font-size: 15px;
                border: 2px solid ${isDark ? '#404040' : '#d1d5db'};
                border-radius: 10px;
                background: ${isDark ? '#2a2a2a' : 'white'};
                color: ${textPrimary};
                font-family: ${this.fontFamily};
                transition: border-color 0.2s ease;
              "
              onfocus="this.style.borderColor='${this.accentColor}'"
              onblur="this.style.borderColor='${isDark ? '#404040' : '#d1d5db'}'"
            >
          </div>
        </div>

        <!-- Code Entreprise (optionnel) -->
        <button id="rse-validate-btn" style="
          width: 100%;
          margin-top: 24px;
          padding: 16px;
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          border: none;
          border-radius: 12px;
          color: white;
          font-size: 16px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s ease;
          box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
          font-family: ${this.fontFamily};
        " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
          Valider
        </button>
      </div>
    `;

    // Attacher l'event listener au bouton de validation
    setTimeout(() => {
      const validateBtn = this.shadowRoot.getElementById('rse-validate-btn');
      if (validateBtn) {
        validateBtn.addEventListener('click', () => this.handleRSEValidation());
      }

      // Attacher l'event listener à la checkbox de covoiturage
      const carpoolCheckbox = this.shadowRoot.getElementById('rse-offer-carpool-checkbox');
      if (carpoolCheckbox) {
        carpoolCheckbox.addEventListener('change', async (e) => {
          const detailsSection = this.shadowRoot.getElementById('rse-carpool-details');
          if (e.target.checked) {
            // Afficher la section
            if (detailsSection) detailsSection.style.display = 'block';
            // Initialiser la carte aller uniquement
            await this.initRSECarpoolMap();
          } else {
            // Masquer la section
            if (detailsSection) detailsSection.style.display = 'none';
          }
        });
      }

      // Attacher l'event listener au slider de détour
      const detourSlider = this.shadowRoot.getElementById('rse-max-detour-time');
      const detourValue = this.shadowRoot.getElementById('rse-detour-value');
      if (detourSlider && detourValue) {
        const isDark = this.getAttribute('data-theme') === 'dark';
        detourSlider.addEventListener('input', (e) => {
          const value = e.target.value;
          detourValue.textContent = `${value} min`;
          // Mettre à jour le gradient du slider (plage 0-20)
          const percentage = (value / 20) * 100;
          e.target.style.background = `linear-gradient(to right, ${this.colorOutbound} 0%, ${this.colorOutbound} ${percentage}%, ${isDark ? '#404040' : '#d1d5db'} ${percentage}%, ${isDark ? '#404040' : '#d1d5db'} 100%)`;
        });
      }
    }, 100);
  }

  async initRSECarpoolMap() {
    const mapContainer = this.shadowRoot.getElementById('rse-map-container');
    if (!mapContainer) return;

    // Créer une nouvelle instance de carte pour le récap RSE
    if (this.rseMap) {
      this.rseMap.remove();
      this.rseMap = null;
    }

    this.rseMap = new maplibregl.Map({
      container: mapContainer,
      style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
      center: this.startCoords || [2.3522, 48.8566],
      zoom: 12
    });

    this.rseMap.on('load', async () => {
      // Ajouter les marqueurs départ et arrivée
      if (this.startCoords) {
        new maplibregl.Marker({ color: this.colorReturn })
          .setLngLat(this.startCoords)
          .addTo(this.rseMap);
      }

      if (this.endCoords) {
        new maplibregl.Marker({ color: this.colorReturn })
          .setLngLat(this.endCoords)
          .addTo(this.rseMap);
      }

      // Dessiner uniquement l'itinéraire aller
      if (this.routeAlternatives && this.routeAlternatives[0]) {
        this.rseMap.addSource('rse-route-outbound', {
          type: 'geojson',
          data: {
            type: 'Feature',
            geometry: this.routeAlternatives[0].geometry
          }
        });

        this.rseMap.addLayer({
          id: 'rse-route-outbound-layer',
          type: 'line',
          source: 'rse-route-outbound',
          paint: {
            'line-color': this.colorReturn,
            'line-width': 5
          }
        });
      }

      // Ajuster la vue pour voir tout
      const bounds = new maplibregl.LngLatBounds();
      if (this.startCoords) bounds.extend(this.startCoords);
      if (this.endCoords) bounds.extend(this.endCoords);
      this.rseMap.fitBounds(bounds, { padding: 50 });
    });
  }

  handleRSEValidation() {
    // Valider les champs obligatoires
    const nameEl = this.shadowRoot.getElementById('rse-user-name');
    const emailEl = this.shadowRoot.getElementById('rse-user-email');
    const phoneEl = this.shadowRoot.getElementById('rse-user-phone');
    
    const name = (nameEl?.value || '').trim();
    const email = (emailEl?.value || '').trim();
    const phone = (phoneEl?.value || '').trim();
    
    if (!name) {
      alert('Veuillez saisir votre nom et prénom');
      nameEl?.focus();
      return;
    }
    
    if (!email) {
      alert('Veuillez saisir votre adresse email');
      emailEl?.focus();
      return;
    }
    
    // Valider le format email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      alert('Veuillez saisir une adresse email valide');
      emailEl?.focus();
      return;
    }
    
    if (!phone) {
      alert('Veuillez saisir votre numéro de téléphone');
      phoneEl?.focus();
      return;
    }
    
    const checkbox = this.shadowRoot.getElementById('rse-offer-carpool-checkbox');
    const wantsToOfferCarpool = checkbox && checkbox.checked;

    // Enregistrer les données RSE avec opt-in covoiturage
    console.log(wantsToOfferCarpool ? '✅ Utilisateur accepte les propositions de covoiturage' : 'ℹ️ Utilisateur ne souhaite pas de covoiturage');
    this.submitRSEData(name, email, phone, wantsToOfferCarpool);
  }

  async submitRSEData(userName, userEmail, userPhone) {
    const isDark = this.theme === 'dark';
    const textPrimary = isDark ? '#ffffff' : '#1d1d1f';
    
    // Trouver le bouton de validation
    const validateBtn = this.shadowRoot.getElementById('rse-validate-btn');
    if (!validateBtn) return;
    
    // Afficher l'état de chargement
    validateBtn.disabled = true;
    validateBtn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 8px; animation: spin 1s linear infinite;">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
      </svg>
      Envoi en cours...
    `;
    
    // Calculer les émissions CO2
    const co2Data = this.calculateRSECO2Emissions();
    
    // Calculer le total
    let totalCO2 = 0;
    Object.values(co2Data).forEach(kg => {
      totalCO2 += parseFloat(kg) || 0;
    });
    // Arrondir à 2 décimales
    totalCO2 = parseFloat(totalCO2.toFixed(2));
    
    // Préparer les données
    const payload = {
      user_name: userName,
      user_email: userEmail,
      user_phone: userPhone,
      company_code: this.companyCode,
      departure: this.shadowRoot.getElementById('from')?.value || '',
      destination: this.shadowRoot.getElementById('to')?.value || '',
      distance_km: this.routeAlternatives && this.routeAlternatives[0] 
        ? (this.routeAlternatives[0].distance / 1000).toFixed(1)
        : 0,
      transport_modes: this.rseTransportData || {},
      co2_emissions: co2Data,
      total_co2: totalCO2,
      has_carpool_offer: false
    };
    
    console.log('📤 Envoi données RSE:', payload);
    
    try {
      const response = await fetch('/api/v2/rse/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        // Déterminer si c'est une mise à jour ou une création
        const isUpdate = result.is_update || false;
        const successTitle = isUpdate ? '🔄 Mise à jour réussie !' : '✅ Enregistrement réussi !';
        const successMessage = isUpdate 
          ? `Merci <strong>${userName}</strong> !<br/>Vos trajets ont été mis à jour. <strong style="color:#fbbf24;">Votre confirmation précédente a été réinitialisée.</strong><br/>Vous recevrez un nouvel email de récapitulatif vendredi.`
          : `Merci <strong>${userName}</strong> !<br/>Un récapitulatif détaillé vous a été envoyé par email.`;
        
        // Remplacer le bouton par un message de confirmation
        validateBtn.outerHTML = `
          <div style="
            margin-top: 24px;
            padding: 32px 24px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border-radius: 16px;
            text-align: center;
            box-shadow: 0 8px 24px rgba(16, 185, 129, 0.4);
            animation: slideInUp 0.5s ease-out;
          ">
            <div style="
              width: 80px;
              height: 80px;
              background: rgba(255, 255, 255, 0.2);
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              margin: 0 auto 20px auto;
            ">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M20 6L9 17l-5-5" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            
            <h3 style="
              margin: 0 0 12px 0;
              font-size: 24px;
              font-weight: 900;
              color: white;
              font-family: ${this.fontFamily};
            ">
              ${successTitle}
            </h3>
            
            <p style="
              margin: 0 0 20px 0;
              font-size: 16px;
              color: rgba(255, 255, 255, 0.95);
              line-height: 1.5;
              font-family: ${this.fontFamily};
            ">
              ${successMessage}
            </p>
            
            <div style="
              display: inline-flex;
              align-items: center;
              gap: 8px;
              padding: 12px 24px;
              background: rgba(255, 255, 255, 0.15);
              border-radius: 10px;
              margin-bottom: 12px;
            ">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span style="
                font-size: 14px;
                font-weight: 600;
                color: white;
                font-family: ${this.fontFamily};
              ">
                ${userEmail}
              </span>
            </div>
            
            <div style="
              padding: 16px;
              background: rgba(255, 255, 255, 0.15);
              border-radius: 12px;
              backdrop-filter: blur(10px);
            ">
              <div style="
                font-size: 13px;
                color: rgba(255, 255, 255, 0.9);
                font-weight: 600;
                margin-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-family: ${this.fontFamily};
              ">
                🌱 VOTRE EMPREINTE CARBONE
              </div>
              <div style="
                font-size: 36px;
                font-weight: 900;
                color: white;
                font-family: ${this.fontFamily};
              ">
                ${totalCO2.toFixed(1)} kg CO₂
              </div>
              <div style="
                font-size: 13px;
                color: rgba(255, 255, 255, 0.85);
                font-family: ${this.fontFamily};
              ">
                par semaine
              </div>
            </div>
          </div>
        `;
      } else {
        // En cas d'erreur, restaurer le bouton
        validateBtn.disabled = false;
        validateBtn.innerHTML = '✅ Valider mon bilan carbone';
        alert(`Erreur: ${result.error || 'Une erreur est survenue'}`);
      }
    } catch (error) {
      console.error('Erreur soumission RSE:', error);
      // En cas d'erreur, restaurer le bouton
      validateBtn.disabled = false;
      validateBtn.innerHTML = '✅ Valider mon bilan carbone';
      alert('Erreur lors de l\'enregistrement. Veuillez réessayer.');
    }
  }

  async submitRSECarpoolOffer(userName, userEmail, userPhone) {
    // Récupérer les données du formulaire
    const fromEl = this.shadowRoot.getElementById('from');
    const toEl = this.shadowRoot.getElementById('to');
    const seatsEl = this.shadowRoot.getElementById('seats');
    const maxDetourTimeEl = this.shadowRoot.getElementById('rse-max-detour-time');

    const departure = (fromEl?.value || '').trim();
    const destination = (toEl?.value || '').trim();
    const seats = parseInt(seatsEl?.value || '4', 10) || 4;
    const max_detour_time = parseInt(maxDetourTimeEl?.value || '10', 10);
    const max_detour_km = 5; // Valeur par défaut

    // Récupérer uniquement les jours où l'utilisateur vient en voiture (solo ou covoiturage)
    const selectedDays = [];
    const weekDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    weekDays.forEach(dayId => {
      const modeIndex = this.rseTransportData[dayId];
      // 0 = voiture solo, 2 = covoiturage
      if (modeIndex === 0 || modeIndex === 2) {
        selectedDays.push(dayId);
      }
    });

    if (selectedDays.length === 0) {
      alert('Aucun jour en voiture sélectionné');
      return;
    }

    // Convertir le tableau de jours en objet avec des booléens pour chaque jour
    const daysObject = {
      monday: selectedDays.includes('monday'),
      tuesday: selectedDays.includes('tuesday'),
      wednesday: selectedDays.includes('wednesday'),
      thursday: selectedDays.includes('thursday'),
      friday: selectedDays.includes('friday'),
      saturday: selectedDays.includes('saturday'),
      sunday: selectedDays.includes('sunday')
    };

    // Validation
    const errors = [];
    if (!departure) errors.push('adresse de départ');
    if (!destination) errors.push("adresse d'arrivée");
    if (selectedDays.length === 0) errors.push('au moins un jour de covoiturage');

    if (errors.length) {
      alert('Merci de renseigner: ' + errors.join(', '));
      return;
    }

    // Construction du payload identique au mode récurrent
    const payload = {
      departure: departure,
      destination: destination,
      departure_coords: this.startCoords,
      destination_coords: this.endCoords,
      // Jours de la semaine
      monday: daysObject.monday,
      tuesday: daysObject.tuesday,
      wednesday: daysObject.wednesday,
      thursday: daysObject.thursday,
      friday: daysObject.friday,
      saturday: daysObject.saturday,
      sunday: daysObject.sunday,
      // Horaires par défaut (09:00 arrivée, 18:00 départ)
      time_outbound: '09:00',
      time_return: '18:00',
      seats: seats,
      max_detour_time: max_detour_time,
      company_id: this.companyId || null,
      // Ne pas envoyer site_id en RSE, laisser l'API le créer/récupérer
      site_name: this.selectedSiteName || null,
      site_address: this.selectedSiteAddress || null,
      site_coords: this.endCoords || null,
      driver_name: userName,
      driver_email: userEmail,
      driver_phone: userPhone,
      // Données de l'itinéraire
      route_outbound: this.routeAlternatives && this.routeAlternatives[0] ? {
        distance: this.routeAlternatives[0].distance,
        duration: this.routeAlternatives[0].duration
      } : null,
      route_return: this.returnRoute || null,
      // Mode RSE
      is_rse: true,
      transport_modes: this.rseTransportData || {}
    };

    console.log('📤 Soumission offre RSE:', payload);

    // Désactiver le bouton pendant l'envoi
    const validateBtn = this.shadowRoot.getElementById('rse-validate-btn');
    const originalText = validateBtn ? validateBtn.textContent : 'Valider';
    if (validateBtn) {
      validateBtn.disabled = true;
      validateBtn.textContent = 'Envoi en cours...';
    }

    try {
      const res = await fetch('/api/v2/offers/recurrent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ error: 'Erreur inconnue' }));
        throw new Error(errorData.error || 'Erreur lors de la création de l\'offre');
      }

      const result = await res.json();

      // Succès
      if (validateBtn) {
        validateBtn.style.display = 'none';
        const msg = document.createElement('div');
        msg.id = 'publish-success-msg';
        msg.setAttribute('role', 'status');
        msg.style.cssText = 'margin:16px auto; padding:16px 18px; background:#ffffff; color:#22c55e; text-align:center; border:1px solid rgba(0,0,0,0.08); border-radius:10px; max-width:520px;';
        msg.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:6px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" fill="#22c55e" opacity="0.12"/><path d="M8 12l2.5 2.5 5.5-5.5" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <span style="font-weight:700;">Publication réussie !</span>
          </div>
          <div style="font-weight:600;">Votre offre de covoiturage RSE a été créée avec succès.</div>
          <div style="font-weight:600;">Un email de confirmation vous a été envoyé.</div>
        `;
        const parent = validateBtn.parentElement || this.shadowRoot;
        parent.insertBefore(msg, validateBtn.nextSibling);
        msg.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }

    } catch (err) {
      console.error('Erreur création offre RSE:', err);
      if (validateBtn) {
        validateBtn.disabled = false;
        validateBtn.textContent = originalText;
      }
      alert((err && err.message) ? err.message : 'Une erreur est survenue. Veuillez réessayer.');
    }
  }

  bindEvents() {
    // Gestion des onglets (sans re-render)
    const tabFind = this.shadowRoot.getElementById("tab-find");
    const tabOffer = this.shadowRoot.getElementById("tab-offer");
    const tabMine = this.shadowRoot.getElementById("tab-mine");
    if (tabFind && tabOffer) {
      tabFind.addEventListener("click", async () => {
        this.saveTabFormState(); // Sauvegarde avant changement
        this.saveTabMapState(); // Sauvegarde la carte
        this.activeTab = 'find';
        this.setAttribute('data-active-tab', 'find');
        await this.updateTabUI();
        // Petit délai pour s'assurer que le DOM est mis à jour
        setTimeout(() => {
          this.restoreTabFormState('find'); // Restaure après changement
          this.restoreTabMapState('find'); // Restaure la carte
        }, 10);
      });
      tabOffer.addEventListener("click", async () => {
        this.saveTabFormState(); // Sauvegarde avant changement
        this.saveTabMapState(); // Sauvegarde la carte
        this.activeTab = 'offer';
        this.setAttribute('data-active-tab', 'offer');
        await this.updateTabUI();
        // Petit délai pour s'assurer que le DOM est mis à jour
        setTimeout(() => {
          this.restoreTabFormState('offer'); // Restaure après changement
          this.restoreTabMapState('offer'); // Restaure la carte
        }, 10);
      });
      if (tabMine) {
        tabMine.addEventListener("click", async () => {
          this.saveTabFormState(); // Sauvegarde avant changement
          this.saveTabMapState(); // Sauvegarde la carte
          this.activeTab = 'mine';
          this.setAttribute('data-active-tab', 'mine');
          await this.updateTabUI();
          this.stopMarkers = []; // Initialize stop markers
        });
      }
    }

    const fromInput = this.shadowRoot.getElementById("from");
    const toInput = this.shadowRoot.getElementById("to");
    const fromList = this.shadowRoot.getElementById("from-suggestions");
    const toList = this.shadowRoot.getElementById("to-suggestions");
    
    // Sélecteur de site (mode B2B)
    const siteSelector = this.shadowRoot.getElementById("site-selector");
    if (siteSelector) {
      siteSelector.addEventListener('change', (e) => {
        const selectedOption = e.target.selectedOptions[0];
        const siteId = e.target.value;
        const siteAddress = selectedOption.getAttribute('data-address');
        const siteName = selectedOption.textContent.trim();
        
        // Stocker le nom et l'adresse du site (pas l'ID du dropdown qui n'existe pas en BDD)
        this.selectedSiteId = siteId || null;
        this.selectedSiteName = siteName;
        this.selectedSiteAddress = siteAddress;
        
        // Récupérer le champ to (peut être hidden)
        const toField = this.shadowRoot.getElementById('to');
        
        if (siteAddress && toField) {
          // Remplir automatiquement l'adresse de destination
          toField.value = siteAddress;
          
          // Géocoder l'adresse pour obtenir les coordonnées
          this.geocodeAddress(siteAddress).then(coords => {
            if (coords) {
              this.endCoords = coords;
              
              // Créer ou mettre à jour le marqueur de destination
              if (this.map) {
                if (this.endMarker) {
                  this.endMarker.setLngLat(coords);
                } else {
                  this.endMarker = new maplibregl.Marker({ color: 'green' })
                    .setLngLat(coords)
                    .addTo(this.map);
                }
              }
              
              console.log('📍 Site sélectionné:', selectedOption.textContent, coords);
            }
          });
        }
      });
    }
    
  const returnCheckbox = this.shadowRoot.getElementById("return");
  const returnViaStops = this.shadowRoot.getElementById("return-via-stops");
  const returnViaStopsField = this.shadowRoot.getElementById("return-via-stops-field");
  const stopsList = this.shadowRoot.getElementById("stops-list");
    const fromTimeSel = this.shadowRoot.getElementById("from-time");
    const toTimeSel = this.shadowRoot.getElementById("to-time");
  const retDateOfferEl = this.shadowRoot.getElementById("return-date-offer");
    const retDateFindEl = this.shadowRoot.getElementById("return-date-find");
  const retTimeSel = this.shadowRoot.getElementById("return-time");
  const radiusRange = this.shadowRoot.getElementById('radius-km');
  const radiusValueEl = this.shadowRoot.getElementById('radius-km-value');
  // Rafraîchir frises horaires quand les heures changent (étape 2)
    if (fromTimeSel) {
      // Initialize display and hook custom picker open
      const fromDisp = this.shadowRoot.getElementById('from-time-display');
      if (fromDisp) {
        fromDisp.textContent = fromTimeSel.value || '08:00';
        fromDisp.addEventListener('click', () => this.openTimePicker('from-time'));
      }
      const fromIcon = this.shadowRoot.getElementById('from-time-icon');
      if (fromIcon) fromIcon.addEventListener('click', () => this.openTimePicker('from-time'));
      fromTimeSel.addEventListener('change', () => {
        if (this.activeTab === 'offer' && this.offerStep === 2) {
          try { this.updateOutboundTimeline(); } catch(_) {}
        }
      });
    }
    if (retTimeSel) {
      const retDisp = this.shadowRoot.getElementById('return-time-display');
      if (retDisp) {
        retDisp.textContent = retTimeSel.value || '17:30';
        retDisp.addEventListener('click', () => this.openTimePicker('return-time'));
      }
      const retIcon = this.shadowRoot.getElementById('return-time-icon');
      if (retIcon) retIcon.addEventListener('click', () => this.openTimePicker('return-time'));
      retTimeSel.addEventListener('change', () => {
        if (this.activeTab === 'offer' && this.offerStep === 2) {
          try { this.updateReturnTimeline(); } catch(_) {}
        }
      });
    }
    if (retDateOfferEl) {
      retDateOfferEl.addEventListener('change', () => {
        if (this.activeTab === 'offer' && this.offerStep === 2) {
          try { this.updateReturnTimeline(); } catch(_) {}
        }
      });
    }

    // Toggle retour sur étape 2: dessine/masque la frise et l'itinéraire retour
    if (returnCheckbox) {
      returnCheckbox.addEventListener('change', async () => {
        if (this.activeTab === 'offer' && this.offerStep === 2) {
          const retCol = this.shadowRoot && this.shadowRoot.getElementById('ret-col');
          if (returnCheckbox.checked) {
            try {
              const returnViaStops = this.shadowRoot.getElementById('return-via-stops');
              const via = (returnViaStops && returnViaStops.checked) ? this.stopCoords.filter(Boolean).slice().reverse() : [];
              if (this.endCoords && this.startCoords) {
                await this.drawReturnRouteOSRM(this.endCoords, this.startCoords, via);
                this.updateReturnTimeline();
              }
              if (retCol) retCol.style.display = '';
            } catch(_) {}
          } else {
            if (retCol) retCol.style.display = 'none';
          }
        }
      });
    }

    // Prix par segment
    this.includeTolls = this.shadowRoot.getElementById('include-tolls');
    if (this.includeTolls) {
      this.includeTolls.addEventListener('change', () => {
        // Recalcule les suggestions sans écraser les valeurs éditées manuellement
        this.updateSegmentPrices();
      });
    }
    
    // Scroll l'input en haut de l'écran au focus (mobile) pour libérer l'espace sous les suggestions
    if (fromInput) fromInput.addEventListener('focus', () => this.scrollAnchorToTop(fromInput));
    if (toInput) toInput.addEventListener('focus', () => this.scrollAnchorToTop(toInput));

    // Sur mobile, désactive le datalist et affiche un panneau custom sous le champ
    if (this.isMobile()) {
      if (fromInput) fromInput.removeAttribute('list');
      if (toInput) toInput.removeAttribute('list');
    }

    const maybeResetOfferFlowOnEdit = () => {
      try {
        if (this.activeTab !== 'offer') return;
        // Si on a déjà confirmé (carte affichée ou bout. calcul/recap visibles), revenir à l'état initial
        const calculateWrapper = this.shadowRoot.getElementById('calculate-btn-wrapper');
        const tripSummary = this.shadowRoot.getElementById('trip-summary');
        const mapBox = this.shadowRoot.getElementById('map-box-container');
        const postConfirmVisible = !!(this.offerConfirmed || (calculateWrapper && calculateWrapper.style.display !== 'none') || (tripSummary && tripSummary.style.display !== 'none') || (mapBox && mapBox.style.display !== 'none'));
        if (postConfirmVisible) this.resetOfferFlowToInitial();
      } catch(_) {}
    };

    fromInput.addEventListener("input", async () => {
      maybeResetOfferFlowOnEdit();
      
      // Ignorer les changements programmatiques
      const inputId = 'from';
      if (this.ignoreNextInputEvent[inputId]) {
        this.ignoreNextInputEvent[inputId] = false;
        return;
      }
      
      // Réinitialiser le flag de sélection quand l'utilisateur tape
      this.addressSelected[inputId] = false;
      
      // Debounce: attendre 300ms après la dernière frappe
      if (this.searchDebounceTimers[inputId]) {
        clearTimeout(this.searchDebounceTimers[inputId]);
      }
      
      this.searchDebounceTimers[inputId] = setTimeout(async () => {
        // Ne pas afficher les résultats si une sélection a déjà été faite
        if (this.addressSelected[inputId]) {
          return;
        }
        const results = await this.searchAddress(fromInput.value, this.isMobile() ? null : fromList);
        
        // Toujours utiliser le panel custom car datalist ne fonctionne pas bien dans Shadow DOM
        this.renderSuggestionsBelow(fromInput, results, async (feature) => {
          const label = feature?.properties?.label || '';
          const coords = Array.isArray(feature?.geometry?.coordinates) ? [feature.geometry.coordinates[0], feature.geometry.coordinates[1]] : null;
          if (!coords) return;
          // En mode "offer", vérifier le type d'adresse
          if (this.activeTab === 'offer') {
            const type = feature?.properties?.type;
            if (type === 'municipality' || type === 'locality') {
              alert('Pour proposer un covoiturage, veuillez saisir une adresse précise (numéro de rue ou point d\'intérêt), pas seulement une ville.\n\nExemple : "12 rue du Stade, Lens" au lieu de "Lens"');
              fromInput.value = '';
              return;
            }
          }
          // Annuler le timer de debounce en cours
          if (this.searchDebounceTimers['from']) {
            clearTimeout(this.searchDebounceTimers['from']);
            delete this.searchDebounceTimers['from'];
          }
          // Marquer cette adresse comme sélectionnée
          this.addressSelected['from'] = true;
          // Marquer le prochain événement input comme programmatique
          this.ignoreNextInputEvent['from'] = true;
          fromInput.value = label;
          this.lastGeocodedValues[fromInput.id] = label;
          // Cacher le panneau de suggestions
          const panel = this.shadowRoot.querySelector('.suggestions-panel');
          if (panel) this.hideSuggestionsPanel(panel);
          await this.setCoordsAndMarkers('start', coords);
          if (this.activeTab === 'find') {
            this.searchCenterCoords = coords.slice();
            if (this.findFilterActive) {
              try { this.drawSearchRadius(this.searchCenterCoords, this.searchRadiusMeters); } catch(_) {}
            }
          }
        });
      }, 300);
    });
    
    toInput.addEventListener("input", async () => {
      maybeResetOfferFlowOnEdit();
      
      // Ignorer les changements programmatiques
      const inputId = 'to';
      if (this.ignoreNextInputEvent[inputId]) {
        this.ignoreNextInputEvent[inputId] = false;
        return;
      }
      
      // Réinitialiser le flag de sélection quand l'utilisateur tape
      this.addressSelected[inputId] = false;
      
      // Debounce: attendre 300ms après la dernière frappe
      if (this.searchDebounceTimers[inputId]) {
        clearTimeout(this.searchDebounceTimers[inputId]);
      }
      
      this.searchDebounceTimers[inputId] = setTimeout(async () => {
        // Ne pas afficher les résultats si une sélection a déjà été faite
        if (this.addressSelected[inputId]) {
          return;
        }
        const results = await this.searchAddress(toInput.value, this.isMobile() ? null : toList);
      
        // Toujours utiliser le panel custom car datalist ne fonctionne pas bien dans Shadow DOM
        this.renderSuggestionsBelow(toInput, results, async (feature) => {
          const label = feature?.properties?.label || '';
          const coords = Array.isArray(feature?.geometry?.coordinates) ? [feature.geometry.coordinates[0], feature.geometry.coordinates[1]] : null;
          if (!coords) return;
          // En mode "offer", vérifier le type d'adresse
          if (this.activeTab === 'offer') {
            const type = feature?.properties?.type;
            if (type === 'municipality' || type === 'locality') {
              alert('Pour proposer un covoiturage, veuillez saisir une adresse précise (numéro de rue ou point d\'intérêt), pas seulement une ville.\n\nExemple : "Stade Bollaert-Delelis, Lens" au lieu de "Lens"');
              toInput.value = '';
              return;
            }
          }
          // Annuler le timer de debounce en cours
          if (this.searchDebounceTimers['to']) {
            clearTimeout(this.searchDebounceTimers['to']);
            delete this.searchDebounceTimers['to'];
          }
          // Marquer cette adresse comme sélectionnée
          this.addressSelected['to'] = true;
          // Marquer le prochain événement input comme programmatique
          this.ignoreNextInputEvent['to'] = true;
          toInput.value = label;
          this.lastGeocodedValues[toInput.id] = label;
          // Cacher le panneau de suggestions
          const panel = this.shadowRoot.querySelector('.suggestions-panel');
          if (panel) this.hideSuggestionsPanel(panel);
          await this.setCoordsAndMarkers('end', coords);
        });
      }, 300);
    });

    fromInput.addEventListener("change", async () => {
      maybeResetOfferFlowOnEdit();
      const label = (fromInput.value || '').trim();
      if (this.activeTab === 'find') {
        const coords = this.featureCache.get(label);
        if (coords) await this.setCoordsAndMarkers('start', coords);
        else await this.geocodeAndPlacePin(label, 'start');
        if (this.startCoords) {
          this.searchCenterCoords = this.startCoords.slice();
          if (this.findFilterActive) {
            try { this.drawSearchRadius(this.searchCenterCoords, this.searchRadiusMeters); } catch(_) {}
          }
        }
      }
    });
    
    toInput.addEventListener("change", async () => {
      maybeResetOfferFlowOnEdit();
      const label = (toInput.value || '').trim();
      if (this.activeTab === 'find') {
        const coords = this.featureCache.get(label);
        if (coords) await this.setCoordsAndMarkers('end', coords);
        else await this.geocodeAndPlacePin(label, 'end');
      }
    });

    if (fromTimeSel) {
      fromTimeSel.addEventListener('change', () => { this.fromTime = fromTimeSel.value; maybeResetOfferFlowOnEdit(); });
    }
    if (toTimeSel) {
      toTimeSel.addEventListener('change', () => { this.toTime = toTimeSel.value; });
    }

    // Changement du rayon via slider (find tab seulement)
    if (radiusRange) {
      const radiusLabel = this.shadowRoot.getElementById('radius-km-label');
      radiusRange.addEventListener('input', () => {
        const km = parseInt(radiusRange.value, 10) || 3;
        this.searchRadiusMeters = km * 1000;
        if (radiusValueEl) radiusValueEl.textContent = km;
        if (this.activeTab === 'find' && this.searchCenterCoords && this.findFilterActive) {
          try { this.drawSearchRadius(this.searchCenterCoords, this.searchRadiusMeters); } catch(_) {}
        }
      });
    }

    if (retDateOfferEl) retDateOfferEl.addEventListener('change', () => this.enforceReturnConstraints());
    if (retTimeSel) retTimeSel.addEventListener('change', () => this.enforceReturnConstraints());

    if (returnViaStops) {
      returnViaStops.addEventListener('change', async () => {
        try { this.updateSegmentPrices(); } catch(_) {}
      });
    }
    
    // Gestion du champ d'ajout d'étape permanent
  const addStopInput = this.shadowRoot.getElementById('add-stop-input');
    const addStopList = this.shadowRoot.getElementById('add-stop-suggestions');
    if (addStopInput) {
      let isProcessing = false; // Flag pour éviter les doubles ajouts
      
      // Autocomplétion
      addStopInput.addEventListener('input', async () => {
        maybeResetOfferFlowOnEdit();
        const results = await this.searchAddress(addStopInput.value, this.isMobile() ? null : addStopList);
        if (this.isMobile()) {
          this.renderSuggestionsBelow(addStopInput, results, async (feature) => {
            if (isProcessing) return; // Éviter le double déclenchement
            isProcessing = true;
            const label = feature?.properties?.label || '';
            const coords = Array.isArray(feature?.geometry?.coordinates) ? [feature.geometry.coordinates[0], feature.geometry.coordinates[1]] : null;
            if (!coords) {
              isProcessing = false;
              return;
            }
            // En mode "offer", vérifier le type d'adresse
            if (this.activeTab === 'offer') {
              const type = feature?.properties?.type;
              if (type === 'municipality' || type === 'locality') {
                alert('Pour les étapes, veuillez saisir une adresse précise (numéro de rue ou point d\'intérêt), pas seulement une ville.');
                addStopInput.value = '';
                isProcessing = false;
                return;
              }
            }
            addStopInput.value = label;
            this.lastGeocodedValues[addStopInput.id] = label;
            // Créer une nouvelle étape
            this.addStopFromInput(label, coords);
            // Vider le champ pour permettre d'ajouter une autre étape
            setTimeout(() => { 
              addStopInput.value = ''; 
              isProcessing = false;
            }, 100);
          });
        }
      });
      
      // Validation au change (sélection d'une suggestion desktop)
      addStopInput.addEventListener('change', async () => {
        maybeResetOfferFlowOnEdit();
        if (isProcessing) return; // Éviter le double déclenchement
        isProcessing = true;
        const val = addStopInput.value.trim();
        if (!val) {
          isProcessing = false;
          return;
        }
        // En mode "offer", on exige une adresse précise pour les étapes
        const requirePrecise = (this.activeTab === 'offer');
        const coords = await this.geocodeAddress(val, requirePrecise);
        if (!coords) {
          isProcessing = false;
          return;
        }
        // Vérifier si c'est une erreur de précision
        if (coords.error === 'precise_required') {
          alert('Pour les étapes, veuillez saisir une adresse précise (numéro de rue ou point d\'intérêt), pas seulement une ville.');
          addStopInput.value = '';
          isProcessing = false;
          return;
        }
        // Créer une nouvelle étape
        this.addStopFromInput(val, coords);
        // Vider le champ
        addStopInput.value = '';
        setTimeout(() => { isProcessing = false; }, 100);
      });
    }
    
    // Délégation: saisie et suppression des étapes créées
    if (stopsList) {
      // focus sur un champ étape => scroll en haut pour bien voir les suggestions
      stopsList.addEventListener('focusin', (e) => {
        const input = e.target.closest('input[data-stop-index]');
        if (input) this.scrollAnchorToTop(input);
      });
      
      stopsList.addEventListener("input", async (e) => {
        maybeResetOfferFlowOnEdit();
        const input = e.target.closest('input[data-stop-index]');
        if (!input) return;
        const dl = this.shadowRoot.getElementById(input.getAttribute('list'));
        const results = await this.searchAddress(input.value, this.isMobile() ? null : dl);
        if (this.isMobile()) {
          this.renderSuggestionsBelow(input, results, async (feature) => {
            const label = feature?.properties?.label || '';
            const coords = Array.isArray(feature?.geometry?.coordinates) ? [feature.geometry.coordinates[0], feature.geometry.coordinates[1]] : null;
            if (!coords) return;
            input.value = label;
            this.lastGeocodedValues[input.id] = label;
            const index = parseInt(input.dataset.stopIndex, 10);
            this.setStopCoords(index, coords);
            this.fitMapToBounds();
          });
        } else {
          this.maybeGeocodeOnSuggestionStop(input, dl);
        }
      });
      
      stopsList.addEventListener("change", async (e) => {
        maybeResetOfferFlowOnEdit();
        const input = e.target.closest('input[data-stop-index]');
        if (input) {
          const index = parseInt(input.dataset.stopIndex, 10);
          const coords = await this.geocodeAddress(input.value);
          if (!coords) return;
          this.setStopCoords(index, coords);
          return;
        }
      });
      
      // Suppression
      stopsList.addEventListener("click", async (e) => {
        const btn = e.target.closest('button[data-remove-stop]');
        if (!btn) return;
        maybeResetOfferFlowOnEdit();
        const index = parseInt(btn.dataset.removeStop, 10);
        this.removeStop(index);
      });
    }

    // Changement de date: réinitialise le flux Offer si actif
    const dateEl = this.shadowRoot.getElementById('date');
    if (dateEl) dateEl.addEventListener('change', maybeResetOfferFlowOnEdit);
    // Assure l'état visuel correct des onglets au chargement
    this.updateTabUI();
    // Mise à jour initiale des prix segment si déjà départ/arrivée
    try { this.updateSegmentPrices(); } catch(_) {}

    // Bouton "Confirmer mon trajet" (étape 1 : affiche la carte)
    const confirmTripBtn = this.shadowRoot.getElementById('confirm-trip-btn');
    if (confirmTripBtn) {
      confirmTripBtn.addEventListener('click', async () => {
        await this.confirmAndShowMap();
      });
    }

    // Bouton "Retour" (barre du wizard)
    const backBtn = this.shadowRoot.getElementById('offer-back-btn');
    if (backBtn) {
      backBtn.addEventListener('click', () => {
        const current = this.offerStep || 1;
        if (current <= 1) return;
        if (current === 2) {
          // Retour à la saisie: réinitialiser le flux et nettoyer les tracés
          this.resetOfferFlowToInitial();
        } else if (current === 3) {
          // Retour à la sélection de trajet aller
          this.currentRouteSelectionMode = 'outbound';
          this.setOfferStep(2);
          // Réafficher les alternatives sur la carte ET regénérer le HTML des cartes
          setTimeout(async () => {
            await this.displayRouteAlternatives();
            const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
            if (routeListEl) {
              routeListEl.innerHTML = this.renderRouteAlternativesHTML();
              this.attachRouteAlternativeListeners();
            }
            this.fitMapToAllAlternatives();
          }, 100);
        } else if (current === 4) {
          // Retour à l'étape précédente (step 3 si retour, sinon step 2)
          const previousStep = this.hasReturnTrip ? 3 : 2;
          this.setOfferStep(previousStep);
        } else if (current === 5) {
          // Retour aux ajustements (step 4)
          this.setOfferStep(4);
        }
      });
    }

    // Bouton "Calculer l'itinéraire" (étape 2 : affiche le récapitulatif)
    const calculateBtn = this.shadowRoot.getElementById('calculate-route-btn');
    if (calculateBtn) {
      calculateBtn.addEventListener('click', async () => {
        await this.calculateAndShowSummary();
      });
    }

    // Bouton "Modifier" dans le récapitulatif
    const editRouteBtn = this.shadowRoot.getElementById('edit-route-btn');
    if (editRouteBtn) {
      editRouteBtn.addEventListener('click', () => {
        // Retour à l'étape 1 (saisie)
        this.offerConfirmed = false;
        this.resetOfferFlowToInitial();
      });
    }

    // Soumission de la proposition (offre)
    const validateBtn = this.shadowRoot.getElementById('validate');
    if (validateBtn) {
      validateBtn.addEventListener('click', async () => {
        if (this.activeTab === 'find') {
          await this.onFindSearchClick();
        } else {
          this.submitCarpoolOffer();
        }
      });
    }
    
    // Bouton "Publier mon offre" (page 5 récapitulatif)
    const validateOfferBtn = this.shadowRoot.getElementById('validate-offer');
    if (validateOfferBtn) {
      validateOfferBtn.addEventListener('click', async () => {
        await this.submitCarpoolOffer();
      });
    }
    
    // Slider de buffer temps dans le récapitulatif (mode récurrent)
    const summaryTimeSlider = this.shadowRoot.getElementById('summary-detour-time-slider');
    const summaryTimeDisplay = this.shadowRoot.getElementById('summary-detour-time-display');
    const summaryAcceptDetours = this.shadowRoot.getElementById('summary-accept-detours');
    const summarySliderSection = this.shadowRoot.getElementById('summary-detour-slider-section');
    
    if (summaryTimeSlider && summaryTimeDisplay && summaryAcceptDetours) {
      const formatTime = (minutes) => {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        if (hours === 0) {
          return `${mins} min`;
        } else if (mins === 0) {
          return `${hours}h 00`;
        } else {
          return `${hours}h ${mins.toString().padStart(2, '0')}`;
        }
      };
      
      const updateSummaryTimeBuffer = () => {
        const minutes = parseInt(summaryTimeSlider.value, 10);
        summaryTimeDisplay.textContent = formatTime(minutes);
        
        // Mettre à jour la couleur de fond du slider
        // Utiliser les vraies valeurs min et max du slider
        const min = parseInt(summaryTimeSlider.min, 10);
        const max = parseInt(summaryTimeSlider.max, 10);
        const percent = ((minutes - min) / (max - min)) * 100;
        summaryTimeSlider.style.background = `linear-gradient(to right, ${this.colorOutbound} 0%, ${this.colorOutbound} ${percent}%, #E5E5EA ${percent}%, #E5E5EA 100%)`;
        
        // Convertir le temps en distance approximative et mettre à jour le buffer
        if (summaryAcceptDetours.checked) {
          const avgSpeedKmH = 50;
          const bufferWidthKm = avgSpeedKmH * (minutes / 60) * 0.5;
          this.updateSummaryDetourBuffers(bufferWidthKm);
        }
      };
      
      const updateDetourVisibility = () => {
        if (summarySliderSection) {
          summarySliderSection.style.display = summaryAcceptDetours.checked ? 'block' : 'none';
        }
        
        if (!summaryAcceptDetours.checked) {
          this.removeSummaryDetourBuffers();
        } else {
          updateSummaryTimeBuffer();
        }
      };
      
      summaryTimeSlider.addEventListener('input', updateSummaryTimeBuffer);
      summaryAcceptDetours.addEventListener('change', updateDetourVisibility);
      
      // Initialisation
      updateDetourVisibility();
      updateSummaryTimeBuffer();
    }
  }

  /**
   * Récupère les jours sélectionnés en mode récurrent
   * @returns {Array} Liste des jours: ['monday', 'tuesday', ...]
   */
  getSelectedDays() {
    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    const selected = [];
    
    days.forEach(day => {
      const checkbox = this.shadowRoot.getElementById(`day-${day}`);
      if (checkbox && checkbox.checked) {
        selected.push(day);
      }
    });
    
    return selected;
  }

  /**
   * Peuple le récapitulatif avec les données du trajet
   * Utilisé en mode récurrent pour remplir directement le récap
   */
  async populateTripSummary() {
    try {
      // Récupération des champs
      const fromEl = this.shadowRoot.getElementById('from');
      const toEl = this.shadowRoot.getElementById('to');

      const departure = (fromEl?.value || '').trim();
      const destination = (toEl?.value || '').trim();

      // Peupler le récapitulatif
      const summaryFrom = this.shadowRoot.getElementById('summary-from');
      const summaryTo = this.shadowRoot.getElementById('summary-to');
      const summaryDistanceOut = this.shadowRoot.getElementById('summary-distance-out');
      const summarySeatsOut = this.shadowRoot.getElementById('summary-seats-out');
      
      // Afficher les adresses
      if (summaryFrom) summaryFrom.textContent = departure;
      if (summaryTo) summaryTo.textContent = destination;
      
      // Calculer et afficher les heures indicatives (mode récurrent)
      if (this.isRecurrentMode()) {
        console.log('Mode récurrent détecté - calcul des heures...');
        const timeAllerEl = this.shadowRoot.getElementById('recurrent-time-outbound');
        const timeRetourEl = this.shadowRoot.getElementById('recurrent-time-return');
        
        console.log('recurrent-time-outbound element:', timeAllerEl);
        console.log('recurrent-time-outbound value:', timeAllerEl?.value);
        console.log('outRoute:', this.outRoute);
        
        if (timeAllerEl && this.outRoute && this.outRoute.duration) {
          const heureArrivee = timeAllerEl.value; // Heure d'arrivée désirée sur le site
          console.log('Heure arrivée récupérée:', heureArrivee);
          
          if (heureArrivee) {
            // Calculer l'heure de départ nécessaire
            const durationMinutes = Math.round(this.outRoute.duration / 60);
            const [hours, minutes] = heureArrivee.split(':').map(Number);
            const arrivalDate = new Date();
            arrivalDate.setHours(hours, minutes, 0, 0);
            
            const departureDate = new Date(arrivalDate.getTime() - durationMinutes * 60 * 1000);
            const departureTime = `${String(departureDate.getHours()).padStart(2, '0')}:${String(departureDate.getMinutes()).padStart(2, '0')}`;
            
            console.log('Temps calculés - Départ:', departureTime, 'Arrivée:', heureArrivee);
            
            // Afficher les heures
            const summaryTimeOutDepart = this.shadowRoot.getElementById('summary-time-out-depart');
            const summaryTimeOutArrivee = this.shadowRoot.getElementById('summary-time-out-arrivee');
            
            console.log('Éléments summary trouvés - Départ:', summaryTimeOutDepart, 'Arrivée:', summaryTimeOutArrivee);
            
            if (summaryTimeOutDepart) summaryTimeOutDepart.textContent = departureTime;
            if (summaryTimeOutArrivee) summaryTimeOutArrivee.textContent = heureArrivee;
          }
        }
        
        // Heures pour le retour
        console.log('recurrent-time-return element:', timeRetourEl);
        console.log('recurrent-time-return value:', timeRetourEl?.value);
        console.log('returnRoute:', this.returnRoute);
        
        if (timeRetourEl && this.returnRoute && this.returnRoute.duration) {
          const heureDepart = timeRetourEl.value; // Heure de départ depuis le site
          console.log('Heure départ retour récupérée:', heureDepart);
          
          if (heureDepart) {
            // Calculer l'heure d'arrivée
            const durationMinutes = Math.round(this.returnRoute.duration / 60);
            const [hours, minutes] = heureDepart.split(':').map(Number);
            const departureDate = new Date();
            departureDate.setHours(hours, minutes, 0, 0);
            
            const arrivalDate = new Date(departureDate.getTime() + durationMinutes * 60 * 1000);
            const arrivalTime = `${String(arrivalDate.getHours()).padStart(2, '0')}:${String(arrivalDate.getMinutes()).padStart(2, '0')}`;
            
            console.log('Temps retour calculés - Départ:', heureDepart, 'Arrivée:', arrivalTime);
            
            // Afficher les heures
            const summaryTimeRetDepart = this.shadowRoot.getElementById('summary-time-ret-depart');
            const summaryTimeRetArrivee = this.shadowRoot.getElementById('summary-time-ret-arrivee');
            
            console.log('Éléments summary retour trouvés - Départ:', summaryTimeRetDepart, 'Arrivée:', summaryTimeRetArrivee);
            
            if (summaryTimeRetDepart) summaryTimeRetDepart.textContent = heureDepart;
            if (summaryTimeRetArrivee) summaryTimeRetArrivee.textContent = arrivalTime;
          }
        }
      }
      
      // Calculer et afficher les heures indicatives (mode RSE)
      if (this.isRseMode()) {
        console.log('Mode RSE détecté - calcul des heures...');
        const timeAllerEl = this.shadowRoot.getElementById('recurrent-time-outbound');
        const timeRetourEl = this.shadowRoot.getElementById('recurrent-time-return');
        
        console.log('recurrent-time-outbound element:', timeAllerEl);
        console.log('recurrent-time-outbound value:', timeAllerEl?.value);
        console.log('outRoute:', this.outRoute);
        
        if (timeAllerEl && this.outRoute && this.outRoute.duration) {
          const heureArrivee = timeAllerEl.value; // Heure d'arrivée désirée sur le site
          console.log('Heure arrivée récupérée:', heureArrivee);
          
          if (heureArrivee) {
            // Calculer l'heure de départ nécessaire
            const durationMinutes = Math.round(this.outRoute.duration / 60);
            const [hours, minutes] = heureArrivee.split(':').map(Number);
            const arrivalDate = new Date();
            arrivalDate.setHours(hours, minutes, 0, 0);
            
            const departureDate = new Date(arrivalDate.getTime() - durationMinutes * 60 * 1000);
            const departureTime = `${String(departureDate.getHours()).padStart(2, '0')}:${String(departureDate.getMinutes()).padStart(2, '0')}`;
            
            console.log('Temps calculés - Départ:', departureTime, 'Arrivée:', heureArrivee);
            
            // Afficher les heures
            const summaryTimeOutDepart = this.shadowRoot.getElementById('summary-time-out-depart');
            const summaryTimeOutArrivee = this.shadowRoot.getElementById('summary-time-out-arrivee');
            
            console.log('Éléments summary trouvés - Départ:', summaryTimeOutDepart, 'Arrivée:', summaryTimeOutArrivee);
            
            if (summaryTimeOutDepart) summaryTimeOutDepart.textContent = departureTime;
            if (summaryTimeOutArrivee) summaryTimeOutArrivee.textContent = heureArrivee;
          }
        }
        
        // Heures pour le retour
        console.log('recurrent-time-return element:', timeRetourEl);
        console.log('recurrent-time-return value:', timeRetourEl?.value);
        console.log('returnRoute:', this.returnRoute);
        
        if (timeRetourEl && this.returnRoute && this.returnRoute.duration) {
          const heureDepart = timeRetourEl.value; // Heure de départ depuis le site
          console.log('Heure départ retour récupérée:', heureDepart);
          
          if (heureDepart) {
            // Calculer l'heure d'arrivée
            const durationMinutes = Math.round(this.returnRoute.duration / 60);
            const [hours, minutes] = heureDepart.split(':').map(Number);
            const departureDate = new Date();
            departureDate.setHours(hours, minutes, 0, 0);
            
            const arrivalDate = new Date(departureDate.getTime() + durationMinutes * 60 * 1000);
            const arrivalTime = `${String(arrivalDate.getHours()).padStart(2, '0')}:${String(arrivalDate.getMinutes()).padStart(2, '0')}`;
            
            console.log('Temps retour calculés - Départ:', heureDepart, 'Arrivée:', arrivalTime);
            
            // Afficher les heures
            const summaryTimeRetDepart = this.shadowRoot.getElementById('summary-time-ret-depart');
            const summaryTimeRetArrivee = this.shadowRoot.getElementById('summary-time-ret-arrivee');
            
            console.log('Éléments summary retour trouvés - Départ:', summaryTimeRetDepart, 'Arrivée:', summaryTimeRetArrivee);
            
            if (summaryTimeRetDepart) summaryTimeRetDepart.textContent = heureDepart;
            if (summaryTimeRetArrivee) summaryTimeRetArrivee.textContent = arrivalTime;
          }
        }
      }
      
      // Distance depuis outRoute
      if (this.outRoute && this.outRoute.distance) {
        const km = (this.outRoute.distance / 1000).toFixed(1);
        if (summaryDistanceOut) summaryDistanceOut.textContent = `${km} km`;
      }
      
      // Nombre de places disponibles
      const seatsEl = this.shadowRoot.getElementById('seats');
      const seatsCount = seatsEl ? parseInt(seatsEl.value, 10) : 4;
      if (summarySeatsOut) {
        summarySeatsOut.textContent = `${seatsCount} place${seatsCount > 1 ? 's' : ''}`;
      }

      // Trajet retour
      const returnCheckbox = this.shadowRoot.getElementById('return');
      const returnVisual = this.shadowRoot.getElementById('return-summary-visual');
      
      // En mode récurrent ou RSE, on affiche toujours le retour. En mode ponctuel, on vérifie la checkbox
      const shouldShowReturn = this.isRecurrentMode() || this.isRseMode() || (returnCheckbox && returnCheckbox.checked);
      
      if (shouldShowReturn) {
        if (returnVisual) returnVisual.style.display = 'block';
        
        const summaryDistanceRet = this.shadowRoot.getElementById('summary-distance-ret');
        const summaryFromRet = this.shadowRoot.getElementById('summary-from-ret');
        const summaryToRet = this.shadowRoot.getElementById('summary-to-ret');
        const summarySeatsRet = this.shadowRoot.getElementById('summary-seats-ret');
        
        // Pour le retour, inverser départ et arrivée
        if (summaryToRet) summaryToRet.textContent = destination;
        if (summaryFromRet) summaryFromRet.textContent = departure;
        
        if (this.returnRoute && this.returnRoute.distance) {
          const km = (this.returnRoute.distance / 1000).toFixed(1);
          if (summaryDistanceRet) summaryDistanceRet.textContent = `${km} km`;
        }
        
        // Nombre de places disponibles pour le retour
        const seatsReturnEl = this.shadowRoot.getElementById('seats-return');
        const seatsReturnCount = seatsReturnEl ? parseInt(seatsReturnEl.value, 10) : seatsCount;
        if (summarySeatsRet) {
          summarySeatsRet.textContent = `${seatsReturnCount} place${seatsReturnCount > 1 ? 's' : ''}`;
        }
      } else {
        if (returnVisual) returnVisual.style.display = 'none';
      }

      // En mode récurrent : afficher les jours et le CO2
      if (this.isRecurrentMode()) {
        const selectedDays = this.getSelectedDays();
        const summaryRecurrentDays = this.shadowRoot.getElementById('summary-recurrent-days');
        const summaryDaysBadges = this.shadowRoot.getElementById('summary-days-badges');
        
        if (summaryRecurrentDays && summaryDaysBadges && selectedDays.length > 0) {
          summaryRecurrentDays.style.display = 'block';
          
          // Générer les badges de jours (même style que page 1)
          const allDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
          const dayLabels = {
            monday: 'Lun',
            tuesday: 'Mar',
            wednesday: 'Mer',
            thursday: 'Jeu',
            friday: 'Ven',
            saturday: 'Sam',
            sunday: 'Dim'
          };
          
          let badgesHTML = '';
          allDays.forEach(day => {
            const isSelected = selectedDays.includes(day);
            const bgColor = isSelected ? this.colorOutbound : 'transparent';
            const textColor = isSelected ? '#fff' : '#8E8E93';
            const borderColor = isSelected ? this.colorOutbound : '#E5E5EA';
            
            badgesHTML += `
              <div style="
                padding: 8px 14px;
                border: 2px solid ${borderColor};
                border-radius: 8px;
                background: ${bgColor};
                color: ${textColor};
                font-size: 13px;
                font-weight: 600;
                font-family: ${this.fontFamily};
                transition: all 0.2s ease;
              ">${dayLabels[day]}</div>
            `;
          });
          
          summaryDaysBadges.innerHTML = badgesHTML;
        }
      } else if (!this.isRseMode()) {
        // Mode ponctuel : afficher la date
        const summaryPonctualDate = this.shadowRoot.getElementById('summary-ponctual-date');
        const summaryDateDisplay = this.shadowRoot.getElementById('summary-date-display');
        const dateEl = this.shadowRoot.getElementById('date');
        
        if (summaryPonctualDate && summaryDateDisplay && dateEl && dateEl.value) {
          summaryPonctualDate.style.display = 'block';
          
          // Formater la date en français
          const date = new Date(dateEl.value + 'T00:00:00');
          const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
          const formattedDate = date.toLocaleDateString('fr-FR', options);
          summaryDateDisplay.textContent = formattedDate.charAt(0).toUpperCase() + formattedDate.slice(1);
        }
      }
      
      if (this.isRecurrentMode()) {
        // Calculer le CO2 évité
        // Formule: ~120g CO2/km en voiture individuelle
        // Si on partage avec 1 passager, on économise ~60g/km chacun
        const co2Value = this.shadowRoot.getElementById('summary-co2-value');
        const co2Detail = this.shadowRoot.getElementById('summary-co2-detail');
        
        if (this.outRoute && this.outRoute.distance) {
          const kmOut = this.outRoute.distance / 1000;
          const kmRet = this.returnRoute ? this.returnRoute.distance / 1000 : 0;
          const totalKm = kmOut + kmRet;
          
          // CO2 économisé par passager (en kg)
          const co2PerKm = 0.120; // 120g CO2 par km
          const co2Saved = (totalKm * co2PerKm * 0.5).toFixed(1); // 50% d'économie en partageant
          
          if (co2Value) {
            co2Value.textContent = `~${co2Saved} kg CO₂ évités`;
          }
          
          if (co2Detail) {
            const nbDays = selectedDays.length;
            if (nbDays > 0) {
              const weeklySavings = (parseFloat(co2Saved) * nbDays).toFixed(1);
              const monthlySavings = (parseFloat(co2Saved) * nbDays * 4).toFixed(0);
              co2Detail.textContent = `par trajet • ${weeklySavings} kg/semaine • ${monthlySavings} kg/mois`;
            }
          }
        }
      }
      
      // En mode RSE : afficher les jours et le CO2
      if (this.isRseMode()) {
        const selectedDays = this.getSelectedDays();
        const summaryRecurrentDays = this.shadowRoot.getElementById('summary-recurrent-days');
        const summaryDaysBadges = this.shadowRoot.getElementById('summary-days-badges');
        
        if (summaryRecurrentDays && summaryDaysBadges && selectedDays.length > 0) {
          summaryRecurrentDays.style.display = 'block';
          
          // Générer les badges de jours (même style que page 1)
          const allDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
          const dayLabels = {
            monday: 'Lun',
            tuesday: 'Mar',
            wednesday: 'Mer',
            thursday: 'Jeu',
            friday: 'Ven',
            saturday: 'Sam',
            sunday: 'Dim'
          };
          
          let badgesHTML = '';
          allDays.forEach(day => {
            const isSelected = selectedDays.includes(day);
            const bgColor = isSelected ? this.colorOutbound : 'transparent';
            const textColor = isSelected ? '#fff' : '#8E8E93';
            const borderColor = isSelected ? this.colorOutbound : '#E5E5EA';
            
            badgesHTML += `
              <div style="
                padding: 8px 14px;
                border: 2px solid ${borderColor};
                border-radius: 8px;
                background: ${bgColor};
                color: ${textColor};
                font-size: 13px;
                font-weight: 600;
                font-family: ${this.fontFamily};
                transition: all 0.2s ease;
              ">${dayLabels[day]}</div>
            `;
          });
          
          summaryDaysBadges.innerHTML = badgesHTML;
        }
        
        // Calculer le CO2 évité
        // Formule: ~120g CO2/km en voiture individuelle
        // Si on partage avec 1 passager, on économise ~60g/km chacun
        const co2Value = this.shadowRoot.getElementById('summary-co2-value');
        const co2Detail = this.shadowRoot.getElementById('summary-co2-detail');
        
        if (this.outRoute && this.outRoute.distance) {
          const kmOut = this.outRoute.distance / 1000;
          const kmRet = this.returnRoute ? this.returnRoute.distance / 1000 : 0;
          const totalKm = kmOut + kmRet;
          
          // CO2 économisé par passager (en kg)
          const co2PerKm = 0.120; // 120g CO2 par km
          const co2Saved = (totalKm * co2PerKm * 0.5).toFixed(1); // 50% d'économie en partageant
          
          if (co2Value) {
            co2Value.textContent = `~${co2Saved} kg CO₂ évités`;
          }
          
          if (co2Detail) {
            const nbDays = selectedDays.length;
            if (nbDays > 0) {
              const weeklySavings = (parseFloat(co2Saved) * nbDays).toFixed(1);
              const monthlySavings = (parseFloat(co2Saved) * nbDays * 4).toFixed(0);
              co2Detail.textContent = `par trajet • ${weeklySavings} kg/semaine • ${monthlySavings} kg/mois`;
            }
          }
        }
      }
      
      // Initialiser et afficher la carte du récapitulatif
      await this.initSummaryMap();
      await this.displaySummaryRoutes();
      
      // Afficher le buffer initial (5 minutes par défaut, correspondant au slider)
      const avgSpeedKmH = 50;
      const defaultMinutes = 5;
      const bufferWidthKm = avgSpeedKmH * (defaultMinutes / 60) * 0.5;
      this.updateSummaryDetourBuffers(bufferWidthKm);
    } catch (error) {
      console.error('Erreur lors du remplissage du récapitulatif:', error);
    }
  }

  /**
   * Étape 1 : Confirme le trajet, affiche la carte et trace l'itinéraire
   */
  async confirmAndShowMap() {
    const confirmBtn = this.shadowRoot.getElementById('confirm-trip-btn');
    const originalText = confirmBtn ? confirmBtn.innerHTML : '';
    
    try {
      // Récupération des champs
      const fromEl = this.shadowRoot.getElementById('from');
      const toEl = this.shadowRoot.getElementById('to');
      
      const departure = (fromEl?.value || '').trim();
      const destination = (toEl?.value || '').trim();
      
      // Mode récurrent : pas de date, mais vérifier les jours sélectionnés
      if (this.isRecurrentMode()) {
        const selectedDays = this.getSelectedDays();
        
        // Validation mode récurrent
        const errors = [];
        if (!departure) errors.push('adresse de départ');
        if (!destination) errors.push("adresse d'arrivée");
        // En mode RSE, pas besoin de sélectionner des jours (calcul empreinte CO2 uniquement)
        if (!this.isRseMode() && selectedDays.length === 0) errors.push('au moins un jour de covoiturage');
        
        if (errors.length) {
          alert('Merci de renseigner: ' + errors.join(', '));
          return;
        }
        
        // En mode récurrent, pas de retour toggle (toujours aller+retour)
        this.hasReturnTrip = true;
      } else if (this.isRseMode()) {
        const selectedDays = this.getSelectedDays();
        
        // Validation mode RSE
        const errors = [];
        if (!departure) errors.push('adresse de départ');
        if (!destination) errors.push("adresse d'arrivée");
        // En mode RSE, pas besoin de sélectionner des jours (calcul empreinte CO2 uniquement)
        if (!this.isRseMode() && selectedDays.length === 0) errors.push('au moins un jour de covoiturage');
        
        if (errors.length) {
          alert('Merci de renseigner: ' + errors.join(', '));
          return;
        }
        
        // En mode RSE, pas de trajet retour (uniquement la distance aller)
        this.hasReturnTrip = false;
      } else {
        // Mode ponctuel : vérifier la date
        const dateEl = this.shadowRoot.getElementById('date');
        const date = (dateEl?.value || '').trim();
        
        // Détecter si trajet retour est coché
        const returnCheckbox = this.shadowRoot.getElementById('return');
        this.hasReturnTrip = returnCheckbox ? returnCheckbox.checked : false;

        // Validation mode ponctuel
        const errors = [];
        if (!departure) errors.push('adresse de départ');
        if (!destination) errors.push("adresse d'arrivée");
        if (!date) errors.push('date');
        if (errors.length) {
          alert('Merci de renseigner: ' + errors.join(', '));
          return;
        }
      }

      // Afficher un état de chargement sur le bouton
      if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 8px; animation: spin 1s linear infinite;">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
          </svg>
          Calcul en cours...
        `;
      }

      // Géocoder et placer les pins
      // En mode "offer", on exige une adresse précise (pas juste une ville)
      const requirePrecise = (this.activeTab === 'offer');
      
      // Vérifier la précision de l'adresse de départ
      if (requirePrecise) {
        const precisionCheck = await this.checkAddressPrecision(departure);
        if (!precisionCheck.isPrecise) {
          if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = originalText;
          }
          alert('Pour proposer un covoiturage, veuillez saisir une adresse de départ précise (numéro de rue ou point d\'intérêt), pas seulement une ville.\n\nExemple : "12 rue du Stade, Lens" au lieu de "Lens"');
          return;
        }
      }
      
      let startCoords = this.featureCache.get(departure);
      if (!startCoords) {
        startCoords = await this.geocodeAddress(departure, requirePrecise);
        if (!startCoords) {
          if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = originalText;
          }
          alert('Impossible de géocoder l\'adresse de départ');
          return;
        }
        // Vérifier si c'est une erreur de précision
        if (startCoords.error === 'precise_required') {
          if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = originalText;
          }
          alert('Pour proposer un covoiturage, veuillez saisir une adresse précise (numéro de rue ou point d\'intérêt), pas seulement une ville.\n\nExemple : "12 rue du Stade, Lens" au lieu de "Lens"');
          return;
        }
      }

      // Vérifier la précision de l'adresse d'arrivée
      if (requirePrecise) {
        const precisionCheck = await this.checkAddressPrecision(destination);
        if (!precisionCheck.isPrecise) {
          if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = originalText;
          }
          alert('Pour proposer un covoiturage, veuillez saisir une adresse d\'arrivée précise (numéro de rue ou point d\'intérêt), pas seulement une ville.\n\nExemple : "Stade Bollaert-Delelis, Lens" au lieu de "Lens"');
          return;
        }
      }
      
      let endCoords = this.featureCache.get(destination);
      if (!endCoords) {
        endCoords = await this.geocodeAddress(destination, requirePrecise);
        if (!endCoords) {
          if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = originalText;
          }
          alert('Impossible de géocoder l\'adresse d\'arrivée');
          return;
        }
        // Vérifier si c'est une erreur de précision
        if (endCoords.error === 'precise_required') {
          if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = originalText;
          }
          alert('Pour proposer un covoiturage, veuillez saisir une adresse précise (numéro de rue ou point d\'intérêt), pas seulement une ville.\n\nExemple : "Stade Bollaert-Delelis, Lens" au lieu de "Lens"');
          return;
        }
      }

      // Placer les marqueurs sur la carte
      if (!this.map) {
        if (confirmBtn) {
          confirmBtn.disabled = false;
          confirmBtn.innerHTML = originalText;
        }
        alert('La carte n\'est pas encore chargée. Veuillez patienter.');
        return;
      }

      if (this.startMarker) this.startMarker.remove();
      this.startMarker = new maplibregl.Marker({ color: "blue" })
        .setLngLat(startCoords)
        .addTo(this.map);
      this.startCoords = startCoords;

      if (this.endMarker) this.endMarker.remove();
      this.endMarker = new maplibregl.Marker({ color: "green" })
        .setLngLat(endCoords)
        .addTo(this.map);
      this.endCoords = endCoords;

      // NOUVEAU : Récupérer les alternatives de trajet
      this.routeAlternatives = await this.fetchRouteAlternatives();
      
      if (!this.routeAlternatives || this.routeAlternatives.length === 0) {
        if (confirmBtn) {
          confirmBtn.disabled = false;
          confirmBtn.innerHTML = originalText;
        }
        alert('Impossible de calculer les itinéraires. Veuillez réessayer.');
        return;
      }

      // Afficher les alternatives sur la carte
      await this.displayRouteAlternatives();

      // Générer le HTML des cartes d'alternatives
      const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
      if (routeListEl) {
        routeListEl.innerHTML = this.renderRouteAlternativesHTML();
        this.attachRouteAlternativeListeners();
      }

      // Ajuster la vue de la carte pour voir tous les trajets
      this.fitMapToAllAlternatives();

      // Étape 2: basculer vers la page de sélection de trajet
      this.setOfferStep(2);

      // Forcer le redimensionnement et la visibilité de la carte
      setTimeout(() => {
        const mapBox = this.shadowRoot.getElementById('map-box-container');
        const mapEl = this.shadowRoot.getElementById('map');
        if (mapBox) {
          mapBox.style.display = 'block';
          mapBox.style.visibility = 'visible';
          const dataTab = this.getAttribute('data-active-tab');
          console.log('🗺️ Carte forcée visible:', mapBox);
          console.log('🗺️ data-active-tab =', dataTab);
          console.log('🗺️ mapBox computed display =', window.getComputedStyle(mapBox).display);
          console.log('🗺️ mapBox computed height =', window.getComputedStyle(mapBox).height);
        }
        if (mapEl) {
          console.log('🗺️ mapEl computed height =', window.getComputedStyle(mapEl).height);
        }
        if (this.map) {
          this.map.resize();
          console.log('🗺️ Carte redimensionnée');
        }
      }, 100);

  // Marque l'état confirmé pour surveiller les modifications ultérieures
  this.offerConfirmed = true;

    } catch (error) {
    this.lastGeocodedValues = {}; // Cache for geocoded values
      alert('Une erreur est survenue lors de la confirmation du trajet.');
      
      // Restaurer le bouton
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = originalText;
      }
    }
  }

  // Remet l'onglet Proposer à l'état initial visuel et nettoie les tracés
  resetOfferFlowToInitial() {
    try {
      this.setOfferStep(1);
      // Nettoyage COMPLET de toutes les sources/layers de la carte
      if (this.map) {
        try {
          // Routes principales
          if (this.map.getSource('route')) { if (this.map.getLayer(this.routeLayerId)) this.map.removeLayer(this.routeLayerId); this.map.removeSource('route'); }
          if (this.map.getSource('return-route')) { if (this.map.getLayer('return-route-line')) this.map.removeLayer('return-route-line'); this.map.removeSource('return-route'); }
          
          // Route sélectionnée
          if (this.map.getSource('selected-offer-route')) { if (this.map.getLayer('selected-offer-route-line')) this.map.removeLayer('selected-offer-route-line'); this.map.removeSource('selected-offer-route'); }
          
          // Rayon de recherche
          if (this.map.getSource('search-radius')) { if (this.map.getLayer('search-radius-fill')) this.map.removeLayer('search-radius-fill'); this.map.removeSource('search-radius'); }
          
          // Routes alternatives (aller et retour) - nettoyer toutes les sources qui commencent par route-alt ou route-return-alt
          const style = this.map.getStyle();
          if (style && style.layers) {
            const layersToRemove = style.layers.filter(l => 
              l.id.startsWith('route-alt-') || l.id.startsWith('route-return-alt-')
            ).map(l => l.id);
            layersToRemove.forEach(layerId => {
              try { this.map.removeLayer(layerId); } catch(e) {}
            });
          }
          if (style && style.sources) {
            const sourcesToRemove = Object.keys(style.sources).filter(s => 
              s.startsWith('route-alt-') || s.startsWith('route-return-alt-')
            );
            sourcesToRemove.forEach(sourceId => {
              try { this.map.removeSource(sourceId); } catch(e) {}
            });
          }
        } catch(_) {}
      }
      // Nettoyer les données calculées
      this.outRoute = null;
      this.returnRoute = null;
      this.lastRouteDistanceMeters = null;
      this.lastReturnRouteDistanceMeters = null;
      this.offerConfirmed = false;
      // Réinitialiser les boutons (et cacher toute surcouche de chargement)
      this.setConfirmButtonIdle();
      this.setCalculateButtonIdle();
      this.loadingCount = 0;
      const overlay = this.shadowRoot && this.shadowRoot.getElementById('map-loading');
      if (overlay) overlay.setAttribute('hidden','');
      // Nettoyer les timelines (aller/retour)
      try {
        const tlOut = this.shadowRoot && this.shadowRoot.getElementById('outbound-timeline');
        const tlRet = this.shadowRoot && this.shadowRoot.getElementById('return-timeline');
        const tlWrap = this.shadowRoot && this.shadowRoot.getElementById('timelines-wrap');
        const retCol = this.shadowRoot && this.shadowRoot.getElementById('ret-col');
        if (tlOut) tlOut.innerHTML = '';
        if (tlRet) tlRet.innerHTML = '';
        if (retCol) retCol.style.display = 'none';
        if (tlWrap) tlWrap.style.display = 'none';
        this.outLegs = null; this.retLegs = null;
      } catch(_) {}
    } catch(_) {}
  }

  /**
   * Étape 3 : Calcule les détails et affiche le récapitulatif
   */
  async calculateAndShowSummary() {
    // En mode RSE étape 4, appeler la fonction de soumission spécifique
    if (this.isRseMode() && this.offerStep === 4) {
      await this.submitRSECarpoolOffer();
      return;
    }

    try {
      // Si aucune route aller sélectionnée, sélectionner automatiquement la première
      if (this.selectedRouteIndex === null && this.routeAlternatives && this.routeAlternatives.length > 0) {
        console.log('📍 Auto-sélection de la première route aller');
        this.selectRouteAlternative(0);
      }
      
      // Si retour activé mais aucune route retour sélectionnée, sélectionner automatiquement la première
      if (this.hasReturnTrip && this.selectedRouteIndexReturn === null && this.routeAlternativesReturn && this.routeAlternativesReturn.length > 0) {
        console.log('📍 Auto-sélection de la première route retour');
        this.selectReturnRouteAlternative(0);
      }
      
      // Récupération des champs
      const fromEl = this.shadowRoot.getElementById('from');
      const toEl = this.shadowRoot.getElementById('to');

      const departure = (fromEl?.value || '').trim();
      const destination = (toEl?.value || '').trim();

      // Afficher un état de chargement sur le bouton
      const calculateBtn = this.shadowRoot.getElementById('calculate-route-btn');
      const originalText = calculateBtn ? calculateBtn.innerHTML : '';
      if (calculateBtn) {
        calculateBtn.disabled = true;
        calculateBtn.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 8px; animation: spin 1s linear infinite;">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
          </svg>
          Calcul en cours...
        `;
      }

      // Vérifier que les données sont bien chargées
      if (!this.outRoute || !this.outRoute.distance) {
        // Restaurer le bouton si échec
        if (calculateBtn) {
          calculateBtn.disabled = false;
          calculateBtn.innerHTML = originalText;
        }
        alert('Impossible de calculer l\'itinéraire. Vérifiez les adresses.');
        return;
      }

      // Attendre un état stable de la carte (style chargé et pas de mouvement) avec fallback pour éviter blocage
      await new Promise(resolve => {
        let attempts = 0;
        const maxAttempts = 20; // ~3s max
        const check = () => {
          try {
            if (!this.map) return resolve();
            const loaded = this.map.isStyleLoaded();
            const moving = this.map.isMoving();
            if (loaded && !moving) {
              return resolve();
            }
          } catch(_) { return resolve(); }
          if (++attempts >= maxAttempts) return resolve();
          setTimeout(check, 150);
        };
        check();
      });
      
      // Ajuster la vue de la carte pour voir tout le trajet
      const coords = [];
      if (this.startCoords) coords.push(this.startCoords);
      if (Array.isArray(this.stopCoords)) {
        this.stopCoords.forEach(c => { if (c) coords.push(c); });
      }
      if (this.endCoords) coords.push(this.endCoords);
      
      if (coords.length > 1) {
        const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
        for (let i = 1; i < coords.length; i++) bounds.extend(coords[i]);
        this.map.fitBounds(bounds, { padding: 60, duration: 400 });
        
        // Attendre la fin de l'animation
        await new Promise(resolve => {
          this.map.once('moveend', resolve);
        });
      }
      
      // Délai de sécurité final
      await new Promise(resolve => setTimeout(resolve, 200));

      // Peupler le récapitulatif
      const summaryFrom = this.shadowRoot.getElementById('summary-from');
      const summaryTo = this.shadowRoot.getElementById('summary-to');
      const summaryDistanceOut = this.shadowRoot.getElementById('summary-distance-out');
      const summarySeatsOut = this.shadowRoot.getElementById('summary-seats-out');
      
      // Afficher les adresses
      if (summaryFrom) summaryFrom.textContent = departure;
      if (summaryTo) summaryTo.textContent = destination;
      
      // Distance depuis outRoute
      if (this.outRoute && this.outRoute.distance) {
        const km = (this.outRoute.distance / 1000).toFixed(1);
        if (summaryDistanceOut) summaryDistanceOut.textContent = `${km} km`;
      }
      
      // Nombre de places disponibles
      const seatsEl = this.shadowRoot.getElementById('seats');
      const seatsCount = seatsEl ? parseInt(seatsEl.value, 10) : 4;
      if (summarySeatsOut) {
        summarySeatsOut.textContent = `${seatsCount} place${seatsCount > 1 ? 's' : ''} disponible${seatsCount > 1 ? 's' : ''}`;
      }
      
      // Prix éditable aller
      const outboundFinalPrice = this.shadowRoot.getElementById('outbound-final-price');
      if (outboundFinalPrice && this.outRoute && this.outRoute.distance) {
        const km = this.outRoute.distance / 1000;
        const includeTolls = this.includeTolls && this.includeTolls.checked;
        const suggestedPrice = this.computeBasePrice(km, includeTolls);
        outboundFinalPrice.value = Math.round(suggestedPrice);
      }

      // Trajet retour
      const returnCheckbox = this.shadowRoot.getElementById('return');
      const returnSection = this.shadowRoot.getElementById('return-summary-section');
      if (returnCheckbox && returnCheckbox.checked) {
        if (returnSection) returnSection.style.display = 'block';
        
        const summaryDistanceRet = this.shadowRoot.getElementById('summary-distance-ret');
        const summaryFromRet = this.shadowRoot.getElementById('summary-from-ret');
        const summaryToRet = this.shadowRoot.getElementById('summary-to-ret');
        const summarySeatsRet = this.shadowRoot.getElementById('summary-seats-ret');
        
        // Pour le retour, inverser départ et arrivée
        if (summaryToRet) summaryToRet.textContent = destination; // Départ du retour = destination de l'aller
        if (summaryFromRet) summaryFromRet.textContent = departure; // Arrivée du retour = départ de l'aller
        
        if (this.returnRoute && this.returnRoute.distance) {
          const km = (this.returnRoute.distance / 1000).toFixed(1);
          if (summaryDistanceRet) summaryDistanceRet.textContent = `${km} km`;
        }
        
        // Nombre de places disponibles pour le retour (peut être différent de l'aller)
        const seatsReturnEl = this.shadowRoot.getElementById('seats-return');
        const seatsReturnCount = seatsReturnEl ? parseInt(seatsReturnEl.value, 10) : seatsCount;
        if (summarySeatsRet) {
          summarySeatsRet.textContent = `${seatsReturnCount} place${seatsReturnCount > 1 ? 's' : ''} disponible${seatsReturnCount > 1 ? 's' : ''}`;
        }
        
        // Prix éditable retour
        const returnFinalPrice = this.shadowRoot.getElementById('return-final-price');
        if (returnFinalPrice && this.returnRoute && this.returnRoute.distance) {
          const km = this.returnRoute.distance / 1000;
          const includeTolls = this.includeTolls && this.includeTolls.checked;
          const suggestedPrice = this.computeBasePrice(km, includeTolls);
          returnFinalPrice.value = Math.round(suggestedPrice);
        }
      } else {
        if (returnSection) returnSection.style.display = 'none';
      }

      // Générer l'encart des prix conseillés
      const pricesContainer = this.shadowRoot.getElementById('summary-recommended-prices');
      if (pricesContainer) {
        let pricesHTML = '';
        
        // Prix aller (total du trajet complet)
        const includeTolls = this.includeTolls && this.includeTolls.checked;
        if (this.outRoute && this.outRoute.distance) {
          const km = this.outRoute.distance / 1000;
          const totalPrice = this.computeBasePrice(km, includeTolls);
          pricesHTML += `
            <div class="summary-recommended-price">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2.5"/>
                <path d="M12 6v6l4 2" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
              </svg>
              <div class="content">
                <div class="label">Prix total conseillé</div>
                <div class="trip-label">Trajet Aller complet</div>
              </div>
              <div class="price">${Math.round(totalPrice)}€</div>
            </div>
          `;
        }
        
        // Prix retour (si activé)
        if (returnCheckbox && returnCheckbox.checked && this.returnRoute && this.returnRoute.distance) {
          const km = this.returnRoute.distance / 1000;
          const totalPrice = this.computeBasePrice(km, includeTolls);
          pricesHTML += `
            <div class="summary-recommended-price">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2.5"/>
                <path d="M12 6v6l4 2" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
              </svg>
              <div class="content">
                <div class="label">Prix total conseillé</div>
                <div class="trip-label">Trajet Retour complet</div>
              </div>
              <div class="price">${Math.round(totalPrice)}€</div>
            </div>
          `;
        }
        
        pricesContainer.innerHTML = pricesHTML;
      }

      // Passer à l'étape récapitulatif (step 4 si pas de retour, step 5 si retour)
      const nextStep = this.hasReturnTrip ? 5 : 4;
      this.setOfferStep(nextStep);

      // Initialiser le contrôle de distance du détour avec visualisation
      await this.initDetourDistanceControl();
      
      // Forcer le redimensionnement de la carte du récapitulatif
      setTimeout(() => {
        if (this.summaryMap) this.summaryMap.resize();
      }, 150);

    } catch (err) {
      console.error('Erreur lors du calcul:', err);
      
      // Restaurer le bouton en cas d'erreur
      const calculateBtn = this.shadowRoot.getElementById('calculate-route-btn');
      const calculateWrapper = this.shadowRoot.getElementById('calculate-btn-wrapper');
      
      if (calculateBtn) {
        calculateBtn.disabled = false;
        calculateBtn.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 8px;">
            <path d="M9 11l3 3L22 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Calculer l'itinéraire
        `;
      }
      
      if (calculateWrapper) {
        calculateWrapper.style.display = 'block';
      }
      
      alert('Erreur lors du calcul de l\'itinéraire: ' + err.message);
    }
  }

  /**
   * Initialise le contrôle de budget temps pour les détours
   */
  async initDetourDistanceControl() {
    const timeSlider = this.shadowRoot.getElementById('detour-time-slider');
    const timeDisplay = this.shadowRoot.getElementById('detour-time-display');
    const checkbox = this.shadowRoot.getElementById('accept-intermediate-passengers');
    const detourControl = this.shadowRoot.getElementById('detour-distance-control');
    
    if (!timeSlider || !timeDisplay || !checkbox) return;
    
    // Créer une carte dédiée pour le récapitulatif
    await this.initSummaryMap();
    
    // Cacher/afficher le contrôle selon la checkbox
    const updateControlVisibility = () => {
      if (detourControl) {
        detourControl.style.display = checkbox.checked ? 'block' : 'none';
      }
      
      const mapContainer = this.shadowRoot.getElementById('summary-map-container');
      if (mapContainer) {
        mapContainer.style.display = checkbox.checked ? 'block' : 'none';
      }
      
      // Enlever le buffer si la checkbox est décochée
      if (!checkbox.checked) {
        this.removeSummaryDetourBuffers();
      } else {
        // Afficher le buffer basé sur le temps (converti en distance)
        const minutes = parseInt(timeSlider.value, 10);
        const avgSpeedKmH = 50;
        const bufferWidthKm = avgSpeedKmH * (minutes / 60) * 0.5;
        this.updateSummaryDetourBuffers(bufferWidthKm);
      }
    };
    
    checkbox.addEventListener('change', updateControlVisibility);
    
    // Formatter le temps en h:mm
    const formatTime = (minutes) => {
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      if (hours === 0) {
        return `${mins} min`;
      } else if (mins === 0) {
        return `${hours}h 00`;
      } else {
        return `${hours}h ${mins.toString().padStart(2, '0')}`;
      }
    };
    
    // Mettre à jour le display du temps quand le slider de temps bouge
    const updateTimeBuffer = () => {
      const minutes = parseInt(timeSlider.value, 10);
      timeDisplay.textContent = formatTime(minutes);
      
      // Synchroniser avec le champ caché max-detour-time
      const maxDetourTimeField = this.shadowRoot.getElementById('max-detour-time');
      if (maxDetourTimeField) {
        maxDetourTimeField.value = minutes;
      }
      
      // Mettre à jour le gradient du slider
      const percent = ((minutes - 15) / (120 - 15)) * 100;
      timeSlider.style.background = `linear-gradient(to right, ${this.colorOutbound} 0%, ${this.colorOutbound} ${percent}%, #E5E5EA ${percent}%, #E5E5EA 100%)`;
      
      // Convertir le temps en distance pour le buffer (vitesse moyenne 50 km/h, facteur 0.5 pour aller-retour)
      const avgSpeedKmH = 50;
      const bufferWidthKm = avgSpeedKmH * (minutes / 60) * 0.5;
      
      // Redessiner le buffer avec la distance calculée depuis le temps
      if (checkbox.checked) {
        this.updateSummaryDetourBuffers(bufferWidthKm);
      }
    };
    
    timeSlider.addEventListener('input', updateTimeBuffer);
    
    // Initialiser l'affichage
    updateControlVisibility();
    updateTimeBuffer(); // Ceci va maintenant aussi mettre à jour le buffer basé sur le temps
  }

  /**
   * Initialise la carte du récapitulatif avec les routes
   */
  async initSummaryMap() {
    const container = this.shadowRoot.getElementById('summary-map');
    if (!container || this.summaryMap) return;
    
    // Créer une nouvelle instance de carte
    const isDark = this.getAttribute('theme') === 'dark';
    const mapStyle = isDark 
      ? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
      : "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
    
    this.summaryMap = new maplibregl.Map({
      container: container,
      style: mapStyle,
      center: [2.8089, 50.4264],
      zoom: 7,
      pitch: 0
    });
    
    this.summaryMap.addControl(new maplibregl.NavigationControl());
    
    // Attendre que la carte soit chargée
    await new Promise(resolve => {
      this.summaryMap.on('load', resolve);
    });
    
    // Force le resize pour s'assurer que la carte prend toute la place
    setTimeout(() => {
      if (this.summaryMap) {
        this.summaryMap.resize();
      }
    }, 100);
    
    // Animation d'entrée premium
    this.summaryMap.easeTo({
      zoom: 8,
      pitch: 25,
      duration: 1500,
      easing: (t) => t * (2 - t)
    });
    
    // Afficher les routes aller et retour
    await this.displaySummaryRoutes();
  }

  /**
   * Affiche les routes aller/retour sur la carte du récapitulatif
   */
  async displaySummaryRoutes() {
    if (!this.summaryMap) {
      console.warn('⚠️ displaySummaryRoutes: summaryMap not initialized');
      return;
    }
    
    console.log('🗺️ displaySummaryRoutes:', {
      hasOutbound: this.selectedRouteIndex !== null,
      hasReturn: this.hasReturnTrip && this.selectedRouteIndexReturn !== null,
      outboundRoute: this.routeAlternatives?.[this.selectedRouteIndex],
      returnRoute: this.routeAlternativesReturn?.[this.selectedRouteIndexReturn],
      mapLoaded: this.summaryMap.loaded()
    });
    
    const coords = [];
    
    // Nettoyer les sources/layers existants
    const layersToRemove = ['summary-route-outbound-line', 'summary-route-return-line'];
    const sourcesToRemove = ['summary-route-outbound', 'summary-route-return'];
    
    layersToRemove.forEach(layerId => {
      if (this.summaryMap.getLayer(layerId)) {
        this.summaryMap.removeLayer(layerId);
      }
    });
    
    sourcesToRemove.forEach(sourceId => {
      if (this.summaryMap.getSource(sourceId)) {
        this.summaryMap.removeSource(sourceId);
      }
    });
    
    // Route aller
    if (this.selectedRouteIndex !== null && this.routeAlternatives && this.routeAlternatives[this.selectedRouteIndex]) {
      const route = this.routeAlternatives[this.selectedRouteIndex];
      
      console.log('➡️ Ajout route aller:', route);
      
      if (route.geometry) {
        this.summaryMap.addSource('summary-route-outbound', {
          type: 'geojson',
          data: {
            type: 'Feature',
            geometry: route.geometry
          }
        });
        
        this.summaryMap.addLayer({
          id: 'summary-route-outbound-line',
          type: 'line',
          source: 'summary-route-outbound',
          paint: {
            'line-color': this.colorOutbound,
            'line-width': 5,
            'line-opacity': 1
          }
        });
        
        console.log('✅ Route aller ajoutée avec couleur:', this.colorOutbound);
        
        // Collecter les coordonnées pour fitBounds
        if (route.geometry.coordinates) {
          coords.push(...route.geometry.coordinates);
        }
      }
    }
    
    // Route retour
    if (this.hasReturnTrip && this.selectedRouteIndexReturn !== null && this.routeAlternativesReturn && this.routeAlternativesReturn[this.selectedRouteIndexReturn]) {
      const route = this.routeAlternativesReturn[this.selectedRouteIndexReturn];
      
      console.log('⬅️ Ajout route retour:', route);
      
      if (route.geometry) {
        this.summaryMap.addSource('summary-route-return', {
          type: 'geojson',
          data: {
            type: 'Feature',
            geometry: route.geometry
          }
        });
        
        this.summaryMap.addLayer({
          id: 'summary-route-return-line',
          type: 'line',
          source: 'summary-route-return',
          paint: {
            'line-color': this.colorReturn,
            'line-width': 5,
            'line-opacity': 1,
            'line-dasharray': [6, 4]
          }
        });
        
        console.log('✅ Route retour ajoutée avec couleur:', this.colorReturn);
        
        // Collecter les coordonnées pour fitBounds
        if (route.geometry.coordinates) {
          coords.push(...route.geometry.coordinates);
        }
      }
    }
    
    // Ajouter les marqueurs de départ/arrivée
    if (this.startCoords) {
      new maplibregl.Marker({ color: this.colorOutbound })
        .setLngLat(this.startCoords)
        .addTo(this.summaryMap);
      coords.push(this.startCoords);
    }
    
    if (this.endCoords) {
      new maplibregl.Marker({ color: "#34C759" })
        .setLngLat(this.endCoords)
        .addTo(this.summaryMap);
      coords.push(this.endCoords);
    }
    
    // Ajuster la vue pour voir toutes les routes
    if (coords.length > 1) {
      const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
      coords.forEach(coord => bounds.extend(coord));
      this.summaryMap.fitBounds(bounds, { padding: 60 });
    }
  }

  /**
   * Affiche ou met à jour les buffers de détour sur la carte du récapitulatif (aller + retour)
   */
  updateSummaryDetourBuffers(km) {
    if (!this.summaryMap) return;
    
    // Supprimer les anciens buffers
    this.removeSummaryDetourBuffers();
    
    // Buffer pour l'aller (ajouté EN PREMIER pour être en dessous)
    if (this.selectedRouteIndex !== null && this.routeAlternatives && this.routeAlternatives[this.selectedRouteIndex]) {
      const route = this.routeAlternatives[this.selectedRouteIndex];
      
      if (route.geometry && route.geometry.coordinates) {
        const bufferPolygon = this.createBufferAroundRoute(route.geometry.coordinates, km);
        
        if (bufferPolygon) {
          try {
            this.summaryMap.addSource('summary-buffer-outbound', {
              type: 'geojson',
              data: {
                type: 'Feature',
                geometry: bufferPolygon
              }
            });
            
            this.summaryMap.addLayer({
              id: 'summary-buffer-outbound-fill',
              type: 'fill',
              source: 'summary-buffer-outbound',
              paint: {
                'fill-color': this.colorOutbound,
                'fill-opacity': 0.15
              }
            });
            
            this.summaryMap.addLayer({
              id: 'summary-buffer-outbound-outline',
              type: 'line',
              source: 'summary-buffer-outbound',
              paint: {
                'line-color': this.colorOutbound,
                'line-width': 1,
                'line-opacity': 0.3
              }
            });
          } catch(err) {
            console.error('Erreur buffer aller:', err);
          }
        }
      }
    }
    
    // Buffer pour le retour
    if (this.hasReturnTrip && this.selectedRouteIndexReturn !== null && this.routeAlternativesReturn && this.routeAlternativesReturn[this.selectedRouteIndexReturn]) {
      const route = this.routeAlternativesReturn[this.selectedRouteIndexReturn];
      
      if (route.geometry && route.geometry.coordinates) {
        const bufferPolygon = this.createBufferAroundRoute(route.geometry.coordinates, km);
        
        if (bufferPolygon) {
          try {
            this.summaryMap.addSource('summary-buffer-return', {
              type: 'geojson',
              data: {
                type: 'Feature',
                geometry: bufferPolygon
              }
            });
            
            this.summaryMap.addLayer({
              id: 'summary-buffer-return-fill',
              type: 'fill',
              source: 'summary-buffer-return',
              paint: {
                'fill-color': this.colorReturn,
                'fill-opacity': 0.15
              }
            });
            
            this.summaryMap.addLayer({
              id: 'summary-buffer-return-outline',
              type: 'line',
              source: 'summary-buffer-return',
              paint: {
                'line-color': this.colorReturn,
                'line-width': 1,
                'line-opacity': 0.3
              }
            });
          } catch(err) {
            console.error('Erreur buffer retour:', err);
          }
        }
      }
    }
    
    // Remettre les routes au-dessus des buffers
    if (this.summaryMap.getLayer('summary-route-outbound-line')) {
      this.summaryMap.moveLayer('summary-route-outbound-line');
    }
    if (this.summaryMap.getLayer('summary-route-return-line')) {
      this.summaryMap.moveLayer('summary-route-return-line');
    }
  }

  /**
   * Supprime les buffers de détour de la carte du récapitulatif
   */
  removeSummaryDetourBuffers() {
    if (!this.summaryMap) return;
    
    const layers = [
      'summary-buffer-outbound-fill',
      'summary-buffer-outbound-outline',
      'summary-buffer-return-fill',
      'summary-buffer-return-outline'
    ];
    
    const sources = [
      'summary-buffer-outbound',
      'summary-buffer-return'
    ];
    
    layers.forEach(layerId => {
      try {
        if (this.summaryMap.getLayer(layerId)) {
          this.summaryMap.removeLayer(layerId);
        }
      } catch(_) {}
    });
    
    sources.forEach(sourceId => {
      try {
        if (this.summaryMap.getSource(sourceId)) {
          this.summaryMap.removeSource(sourceId);
        }
      } catch(_) {}
    });
  }

  /**
   * Soumet l'offre de covoiturage au backend si l'utilisateur est connecté.
   * Contrat:
   * - lit: from (#from), to (#to), date (#date), heure de départ (#from-time), places (#seats)
   * - construit: { user_id, departure, destination, datetime: "YYYY-MM-DD HH:MM", seats, comment }
   * - POST /api/carpool
   */
  async submitCarpoolOffer() {
    try {
      // ✅ V2: Collecter email/nom/téléphone au lieu de userId
      const driverNameEl = this.shadowRoot.getElementById('driver-name');
      const driverEmailEl = this.shadowRoot.getElementById('driver-email');
      const driverPhoneEl = this.shadowRoot.getElementById('driver-phone');

      const driverName = (driverNameEl?.value || '').trim();
      const driverEmail = (driverEmailEl?.value || '').trim();
      const driverPhone = (driverPhoneEl?.value || '').trim();

      // Validation des coordonnées conducteur
      if (!driverName) {
        alert("Veuillez renseigner votre nom complet.");
        return;
      }
      if (!driverEmail) {
        alert("Veuillez renseigner votre email.");
        return;
      }
      
      // Téléphone optionnel mais conseillé
      if (!driverPhone) {
        const confirmWithoutPhone = confirm("Attention : Sans numéro de téléphone, les passagers ne pourront pas vous contacter directement et vous ne recevrez pas de suivi WhatsApp. Souhaitez-vous continuer malgré tout ?");
        if (!confirmWithoutPhone) {
          return;
        }
      }
      
      // Validation basique email
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(driverEmail)) {
        alert("Veuillez renseigner un email valide.");
        return;
      }

      const fromEl = this.shadowRoot.getElementById('from');
      const toEl = this.shadowRoot.getElementById('to');
      const dateEl = this.shadowRoot.getElementById('date');
      const fromTimeEl = this.shadowRoot.getElementById('from-time');
      const toTimeEl = this.shadowRoot.getElementById('to-time');
      const seatsEl = this.shadowRoot.getElementById('seats');
      const maxDetourKmEl = this.shadowRoot.getElementById('max-detour-km');
      const maxDetourTimeEl = this.shadowRoot.getElementById('max-detour-time');
      const returnCheckbox = this.shadowRoot.getElementById('return');
      const retDateOfferEl = this.shadowRoot.getElementById('return-date-offer');
      const retTimeEl = this.shadowRoot.getElementById('return-time');
      const returnViaStops = this.shadowRoot.getElementById('return-via-stops');
      const seatsReturnEl = this.shadowRoot.getElementById('seats-return');

      const departure = (fromEl?.value || '').trim();
      const destination = (toEl?.value || '').trim();
      
      // Mode récurrent vs RSE vs ponctuel : validation différente
      if (this.isRecurrentMode() || this.isRseMode()) {
        // Mode récurrent ou RSE : pas de date/time, mais jours + heures aller/retour
        const selectedDays = this.getSelectedDays();
        const timeOutboundEl = this.shadowRoot.getElementById('recurrent-time-outbound');
        const timeReturnEl = this.shadowRoot.getElementById('recurrent-time-return');
        const timeOutbound = (timeOutboundEl?.value || '').trim();
        const timeReturn = (timeReturnEl?.value || '').trim();
        
        const errors = [];
        if (!departure) errors.push('adresse de départ');
        if (!destination) errors.push("adresse d'arrivée");
        // En mode RSE, pas besoin de sélectionner des jours
        if (!this.isRseMode() && selectedDays.length === 0) errors.push('au moins un jour de covoiturage');
        if (!timeOutbound) errors.push("heure d'arrivée sur site");
        if (!timeReturn) errors.push("heure de départ du site");
        
        if (errors.length) {
          alert('Merci de renseigner: ' + errors.join(', '));
          return;
        }
        
        // Construire le payload pour l'API récurrente
        // selectedDays déjà déclaré plus haut
        const daysPayload = {
          monday: selectedDays.includes('monday'),
          tuesday: selectedDays.includes('tuesday'),
          wednesday: selectedDays.includes('wednesday'),
          thursday: selectedDays.includes('thursday'),
          friday: selectedDays.includes('friday'),
          saturday: selectedDays.includes('saturday'),
          sunday: selectedDays.includes('sunday')
        };
        
        // Récupérer company_id
        const companyId = this.getAttribute('data-company-id') || this.getAttribute('company-id');
        
        if (!companyId) {
          alert('Erreur: company_id manquant');
          return;
        }
        
        // Vérifier que le site a été sélectionné
        if (!this.selectedSiteName || !this.selectedSiteAddress) {
          alert('Erreur: veuillez sélectionner un site de destination');
          return;
        }
        
        const payload = {
          driver_name: driverName,
          driver_email: driverEmail,
          driver_phone: driverPhone,
          company_id: parseInt(companyId),
          site_name: this.selectedSiteName,
          site_address: this.selectedSiteAddress,
          site_coords: this.endCoords,
          departure,
          destination,
          departure_coords: this.startCoords,
          destination_coords: this.endCoords,
          time_outbound: timeOutbound,
          time_return: timeReturn,
          ...daysPayload,
          seats: parseInt(this.shadowRoot.getElementById('seats')?.value || 4),
          max_detour_time: parseInt(this.shadowRoot.getElementById('summary-detour-time-slider')?.value || 5),
          route_outbound: this.routeAlternatives?.[this.selectedRouteIndex] || null,
          route_return: this.routeAlternativesReturn?.[this.selectedRouteIndexReturn] || null,
          color_outbound: this.colorOutbound,
          color_return: this.colorReturn
        };
        
        // Mettre le bouton en mode chargement (spinner inline)
        const btnLoading = this.shadowRoot.getElementById('validate-offer') || this.shadowRoot.getElementById('validate');
        if (btnLoading) {
          btnLoading.disabled = true;
          btnLoading.innerHTML = `<span style="width:16px;height:16px;border:2px solid rgba(0,0,0,0.15);border-top-color:${this.getAttribute('theme') === 'dark' ? '#fff' : '#000'};border-radius:50%;display:inline-block;vertical-align:middle;animation: spin 1s linear infinite;"></span><span style="margin-left:8px;vertical-align:middle;">Envoi…</span>`;
        }
        
        // Désactiver le bouton pendant l'envoi
        const validateBtn = this.shadowRoot.getElementById('validate');
        if (validateBtn) {
          validateBtn.disabled = true;
          validateBtn.textContent = 'Envoi…';
        }
        
        try {
          const res = await fetch('/api/v2/offers/recurrent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload)
          });
          
          if (!res.ok) {
            const errorData = await res.json().catch(() => ({ error: 'Erreur inconnue' }));
            throw new Error(errorData.error || 'Erreur lors de la création de l\'offre');
          }
          
          const result = await res.json();
          
          // Succès - masquer le bouton et afficher un message centré vert sur fond blanc
          const btnSuccess = this.shadowRoot.getElementById('validate-offer') || this.shadowRoot.getElementById('validate');
          if (btnSuccess) {
            btnSuccess.style.display = 'none';
            const msg = document.createElement('div');
            msg.id = 'publish-success-msg';
            msg.setAttribute('role', 'status');
            msg.style.cssText = 'margin:16px auto; padding:16px 18px; background:#ffffff; color:#22c55e; text-align:center; border:1px solid rgba(0,0,0,0.08); border-radius:10px; max-width:520px;';
            msg.innerHTML = `
              <div style="display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:6px;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" fill="#22c55e" opacity="0.12"/><path d="M8 12l2.5 2.5 5.5-5.5" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                <span style="font-weight:700;">Publication réussie !</span>
              </div>
              <div style="font-weight:600;">Votre offre de covoiturage a été créée avec succès.</div>
              <div style="font-weight:600;">Un email de confirmation vous a été envoyé.</div>
            `;
            // Insérer juste après l'ancien bouton
            const parent = btnSuccess.parentElement || this.shadowRoot; 
            parent.insertBefore(msg, btnSuccess.nextSibling);
            msg.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
          
        } catch (err) {
          console.error('Erreur création offre récurrente:', err);
          const btnBack = this.shadowRoot.getElementById('validate-offer') || this.shadowRoot.getElementById('validate');
          if (btnBack) {
            btnBack.disabled = false;
            btnBack.textContent = 'Publier mon offre';
          }
          alert((err && err.message) ? err.message : 'Une erreur est survenue. Veuillez réessayer.');
        } finally {
          if (validateBtn) {
            validateBtn.disabled = false;
            validateBtn.textContent = 'Valider';
          }
        }
        
        return;
        
      } else {
        // Mode ponctuel : vérifier date et time
        const date = (dateEl?.value || '').trim(); // YYYY-MM-DD
        const time = (fromTimeEl?.value || '').trim(); // HH:MM
        const seats = parseInt(seatsEl?.value || '1', 10) || 1;
        const max_detour_km = parseInt(maxDetourKmEl?.value || '5', 10);
        const max_detour_time = parseInt(maxDetourTimeEl?.value || '60', 10);

        // validations minimales
        const errors = [];
        if (!departure) errors.push('adresse de départ');
        if (!destination) errors.push("adresse d'arrivée");
        if (!date) errors.push('date');
        if (!time) errors.push('heure de départ');
        if (errors.length) {
          alert('Merci de renseigner: ' + errors.join(', '));
          return;
        }

        const datetime = `${date} ${time}:00`; // Format MySQL: YYYY-MM-DD HH:MM:SS

        // Collecte des étapes (labels + coords) et horaires d'étapes si présents
        const stopInputs = Array.from(this.shadowRoot.querySelectorAll('input[data-stop-index]'));
        const stops = stopInputs.map(inp => {
          const idx = parseInt(inp.dataset.stopIndex, 10);
          const label = (inp.value || '').trim();
          const coords = Array.isArray(this.stopCoords?.[idx]) ? this.stopCoords[idx] : null;
          const timeSel = this.shadowRoot.querySelector(`select[data-stop-time-index="${idx}"]`);
          const timeVal = timeSel ? (timeSel.value || '') : (this.stopTimes?.[idx] || '');
          return { index: idx, label, coords, time: timeVal };
        });

      // Prix par segment (aller/retour)
      const segmentPricesOut = Array.isArray(this.segmentPricesOut) ? this.segmentPricesOut : [];
      const segmentPricesRet = Array.isArray(this.segmentPricesRet) ? this.segmentPricesRet : [];
      const includeTolls = !!(this.includeTolls && this.includeTolls.checked);

      // Distances, durées et coords de base
      const details = {
        fromTime: time,
        toTime: (toTimeEl?.value || '').trim(),
        fromCoords: Array.isArray(this.startCoords) ? this.startCoords : null,
        toCoords: Array.isArray(this.endCoords) ? this.endCoords : null,
        stadiumCoords: Array.isArray(this.stadiumCoords) ? this.stadiumCoords : null,
        distanceMeters: {
          outbound: Number.isFinite(this.lastRouteDistanceMeters) ? this.lastRouteDistanceMeters : null,
          return: Number.isFinite(this.lastReturnRouteDistanceMeters) ? this.lastReturnRouteDistanceMeters : null
        },
        durationSeconds: {
          outbound: (this.selectedRouteIndex !== null && this.routeAlternatives?.[this.selectedRouteIndex]) ? this.routeAlternatives[this.selectedRouteIndex].duration : null,
          return: (returnCheckbox?.checked && this.selectedRouteIndexReturn !== null && this.routeAlternativesReturn?.[this.selectedRouteIndexReturn]) ? this.routeAlternativesReturn[this.selectedRouteIndexReturn].duration : null
        },
        stops,
        prices: {
          out: segmentPricesOut,
          ret: segmentPricesRet
        },
        includeTolls,
        returnTrip: {
          enabled: !!(returnCheckbox && returnCheckbox.checked),
          date: (retDateOfferEl?.value || '').trim(),
          time: (retTimeEl?.value || '').trim(),
          viaStops: !!(returnViaStops && returnViaStops.checked),
          seats: (returnCheckbox && returnCheckbox.checked && seatsReturnEl) ? parseInt(seatsReturnEl.value || '4', 10) : seats
        }
      };

      // Nouveaux champs pour le flux avancé
      const acceptPassengersCheckbox = this.shadowRoot.getElementById('accept-intermediate-passengers');
      const accept_passengers_on_route = acceptPassengersCheckbox ? acceptPassengersCheckbox.checked : true;
      
      // Places disponibles aller et retour
      const seats_outbound = seats; // Utilise le champ seats principal pour l'aller
      const seats_return = (returnCheckbox && returnCheckbox.checked && seatsReturnEl) ? parseInt(seatsReturnEl.value || seats, 10) : null;
      
      // Itinéraires sélectionnés (geometries + metadata)
      let route_outbound = null;
      let route_return = null;
      
      // Récupérer l'itinéraire aller sélectionné
      if (this.selectedRouteIndex !== null && Array.isArray(this.routeAlternatives) && this.routeAlternatives[this.selectedRouteIndex]) {
        const selectedRoute = this.routeAlternatives[this.selectedRouteIndex];
        route_outbound = {
          geometry: selectedRoute.geometry,
          distance: selectedRoute.distance,
          duration: selectedRoute.duration,
          legs: selectedRoute.legs,
          toll: selectedRoute.toll || false,
          highways: selectedRoute.highways || false
        };
      }
      
      // Récupérer l'itinéraire retour sélectionné (si activé)
      if (returnCheckbox && returnCheckbox.checked && this.selectedRouteIndexReturn !== null && Array.isArray(this.routeAlternativesReturn) && this.routeAlternativesReturn[this.selectedRouteIndexReturn]) {
        const selectedReturnRoute = this.routeAlternativesReturn[this.selectedRouteIndexReturn];
        route_return = {
          geometry: selectedReturnRoute.geometry,
          distance: selectedReturnRoute.distance,
          duration: selectedReturnRoute.duration,
          legs: selectedReturnRoute.legs,
          toll: selectedReturnRoute.toll || false,
          highways: selectedReturnRoute.highways || false
        };
      }

      // Ne pas calculer les buffers côté frontend (trop lent!)
      // Le backend les calculera si nécessaire
      
      // Construire return_datetime si retour activé (format MySQL DATETIME)
      let return_datetime = null;
      if (returnCheckbox && returnCheckbox.checked && details.returnTrip.date && details.returnTrip.time) {
        return_datetime = `${details.returnTrip.date} ${details.returnTrip.time}`;
      }
      
      // ✅ V2: Payload avec email au lieu de user_id
      const payload = {
        driver_name: driverName,
        driver_email: driverEmail,
        driver_phone: driverPhone,
        departure,
        destination,
        datetime,
        seats,
        comment: '',
        details,
        accept_passengers_on_route,
        seats_outbound,
        seats_return,
        route_outbound,
        route_return,
        return_datetime,
        max_detour_km,
        max_detour_time,
        event_id: this.eventId,
        event_name: this.eventName,
        event_location: this.eventLocation,
        event_date: this.eventDate,
        event_time: this.eventTime,
        page_url: this.getAttribute('page-url') || window.location.href,
        color_outbound: this.colorOutbound,
        color_return: this.colorReturn
      };

      // Mettre le bouton en mode chargement (spinner inline)
      const btnLoading2 = this.shadowRoot.getElementById('validate-offer') || this.shadowRoot.getElementById('validate');
      if (btnLoading2) {
        btnLoading2.disabled = true;
        btnLoading2.innerHTML = `<span style="width:16px;height:16px;border:2px solid rgba(0,0,0,0.15);border-top-color:${this.getAttribute('theme') === 'dark' ? '#fff' : '#000'};border-radius:50%;display:inline-block;vertical-align:middle;animation: spin 1s linear infinite;"></span><span style="margin-left:8px;vertical-align:middle;">Envoi…</span>`;
      }
      
      // Utiliser le bouton validate-offer si on est à l'étape finale, sinon validate
      const btn = this.shadowRoot.getElementById('validate-offer') || this.shadowRoot.getElementById('validate');
      if (btn) { btn.disabled = true; btn.textContent = 'Envoi…'; }
      
      // ✅ V2: Appeler /api/v2/offers au lieu de /api/carpool
      const res = await fetch('/api/v2/offers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const tx = await res.text().catch(() => '');
        if (res.status === 400 && /deja|déjà|duplicate/i.test(tx)) {
          alert('Limite atteinte: un seul covoiturage par jour est autorisé.');
          const btn2 = this.shadowRoot.getElementById('validate-offer') || this.shadowRoot.getElementById('validate');
          if (btn2) { btn2.disabled = false; btn2.textContent = 'Publier mon offre'; }
          return;
        }
        throw new Error(`Echec (${res.status}) ${tx}`);
      }
      // Succès - masquer le bouton et afficher un message centré vert sur fond blanc
      const btnSuccess2 = this.shadowRoot.getElementById('validate-offer') || this.shadowRoot.getElementById('validate');
      if (btnSuccess2) {
        btnSuccess2.style.display = 'none';
        const msg2 = document.createElement('div');
        msg2.id = 'publish-success-msg';
        msg2.setAttribute('role', 'status');
        msg2.style.cssText = 'margin:16px auto; padding:16px 18px; background:#ffffff; color:#22c55e; text-align:center; border:1px solid rgba(0,0,0,0.08); border-radius:10px; max-width:520px;';
        msg2.innerHTML = `
          <div style=\"display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:6px;\">
            <svg width=\"20\" height=\"20\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><circle cx=\"12\" cy=\"12\" r=\"10\" fill=\"#22c55e\" opacity=\"0.12\"/><path d=\"M8 12l2.5 2.5 5.5-5.5\" stroke=\"#22c55e\" stroke-width=\"2.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/></svg>
            <span style=\"font-weight:700;\">Publication réussie !</span>
          </div>
          <div style=\"font-weight:600;\">Votre offre de covoiturage a été créée avec succès.</div>
          <div style=\"font-weight:600;\">Un email de confirmation vous a été envoyé.</div>
        `;
        const parent2 = btnSuccess2.parentElement || this.shadowRoot;
        parent2.insertBefore(msg2, btnSuccess2.nextSibling);
        msg2.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      } // Fin du bloc else (mode ponctuel)
    } catch (err) {
      console.error('submitCarpoolOffer error', err);
      
      const btnBack2 = this.shadowRoot.getElementById('validate-offer') || this.shadowRoot.getElementById('validate');
      if (btnBack2) {
        btnBack2.disabled = false;
        btnBack2.textContent = 'Publier mon offre';
      }
      alert("Désolé, l'enregistrement a échoué. Réessayez plus tard.");
    }
  }

  setMapLoading(isLoading) {
    const overlay = this.shadowRoot && this.shadowRoot.getElementById('map-loading');
    if (!overlay) return;
    if (isLoading) {
      this.loadingCount = (this.loadingCount || 0) + 1;
      overlay.removeAttribute('hidden');
    } else {
      this.loadingCount = Math.max(0, (this.loadingCount || 0) - 1);
      if (this.loadingCount === 0) {
        overlay.setAttribute('hidden', '');
      }
    }
  }

  optionMatches(datalist, value) {
    if (!datalist || !value) return false;
    const v = value.trim();
    return Array.from(datalist.options).some(opt => opt.value === v);
  }

  async maybeGeocodeOnSuggestionStartEnd(inputEl, datalist, type) {
    const val = (inputEl && inputEl.value || '').trim();
    if (!val) return;
    if (!this.optionMatches(datalist, val)) return; // pas une suggestion exacte
    if (this.lastGeocodedValues[inputEl.id] === val) return; // déjà géocodé
    const cached = this.featureCache.get(val);
    if (cached) {
      await this.setCoordsAndMarkers(type, cached);
      if (type === 'start' && this.activeTab === 'find' && this.startCoords) {
        this.searchCenterCoords = this.startCoords.slice();
        if (this.findFilterActive) {
          try { this.drawSearchRadius(this.searchCenterCoords, this.searchRadiusMeters); } catch(_) {}
          try { this.renderFindOffersFiltered(); } catch(_) {}
        }
      }
    } else {
      await this.geocodeAndPlacePin(val, type);
      if (type === 'start' && this.activeTab === 'find' && this.startCoords) {
        this.searchCenterCoords = this.startCoords.slice();
        if (this.findFilterActive) {
          try { this.drawSearchRadius(this.searchCenterCoords, this.searchRadiusMeters); } catch(_) {}
          try { this.renderFindOffersFiltered(); } catch(_) {}
        }
      }
    }
    this.lastGeocodedValues[inputEl.id] = val;
    this.fitMapToBounds();
  }

  async maybeGeocodeOnSuggestionStop(inputEl, datalist) {
    const val = (inputEl && inputEl.value || '').trim();
    if (!val) return;
    if (!this.optionMatches(datalist, val)) return;
    if (this.lastGeocodedValues[inputEl.id] === val) return;
    const index = parseInt(inputEl.dataset.stopIndex, 10);
    const cached = this.featureCache.get(val);
    if (cached) {
      this.setStopCoords(index, cached);
    } else {
      // En mode "offer", on exige une adresse précise pour les étapes aussi
      const requirePrecise = (this.activeTab === 'offer');
      const coords = await this.geocodeAddress(val, requirePrecise);
      if (!coords) return;
      // Vérifier si c'est une erreur de précision
      if (coords.error === 'precise_required') {
        alert('Pour les étapes, veuillez saisir une adresse précise (numéro de rue ou point d\'intérêt), pas seulement une ville.');
        // Vider le champ invalide
        if (inputEl) inputEl.value = '';
        return;
      }
      this.setStopCoords(index, coords);
    }
    this.lastGeocodedValues[inputEl.id] = val;
    if (this.startCoords && this.endCoords) {
      await this.drawRouteOSRM();
    }
    this.fitMapToBounds();
  }

  addStopInput() {
    const stopsList = this.shadowRoot.getElementById('stops-list');
    if (!stopsList) return;
    const index = this.nextStopIndex();
    const dlId = `stop-suggestions-${index}`;
    const row = document.createElement('div');
    row.className = 'stop-row';
    row.dataset.index = String(index);
    row.innerHTML = `
      <span class="stop-bullet" aria-hidden="true"></span>
      <input id="stop-${index}" data-stop-index="${index}" autocomplete="off" placeholder="Étape intermédiaire" list="${dlId}" />
      <datalist id="${dlId}"></datalist>
      <button type="button" data-remove-stop="${index}" class="btn-remove-stop" aria-label="Supprimer l'étape" title="Supprimer l'étape"><span class="icon-minus" aria-hidden="true"></span></button>
    `;
    // Insérer avant le champ "add-stop-field" (qui reste toujours à la fin)
    const addStopField = stopsList.querySelector('.add-stop-field');
    if (addStopField) {
      stopsList.insertBefore(row, addStopField);
    } else {
      stopsList.appendChild(row);
    }
  }
  
  // Ajoute une étape depuis le champ permanent
  addStopFromInput(label, coords) {
    if (this.activeTab === 'offer' && this.offerConfirmed) {
      this.resetOfferFlowToInitial();
    }
    const stopsList = this.shadowRoot.getElementById('stops-list');
    if (!stopsList) return;
    const index = this.nextStopIndex();
    const dlId = `stop-suggestions-${index}`;
    const row = document.createElement('div');
    row.className = 'stop-row';
    row.dataset.index = String(index);
    row.innerHTML = `
      <span class="stop-bullet" aria-hidden="true"></span>
      <input id="stop-${index}" data-stop-index="${index}" autocomplete="off" placeholder="Étape intermédiaire" list="${dlId}" value="${label.replace(/"/g, '&quot;')}" />
      <datalist id="${dlId}"></datalist>
      <button type="button" data-remove-stop="${index}" class="btn-remove-stop" aria-label="Supprimer l'étape" title="Supprimer l'étape"><span class="icon-minus" aria-hidden="true"></span></button>
    `;
    // Insérer avant le champ "add-stop-field"
    const addStopField = stopsList.querySelector('.add-stop-field');
    if (addStopField) {
      stopsList.insertBefore(row, addStopField);
    } else {
      stopsList.appendChild(row);
    }
    // Placer le marqueur
    this.setStopCoords(index, coords);
  }

  nextStopIndex() {
    // Trouve le prochain index libre
    let idx = 0;
    while (this.stopCoords[idx] !== undefined) idx++;
    return idx;
  }

  setStopCoords(index, coords) {
    if (this.activeTab === 'offer' && this.offerConfirmed) {
      this.resetOfferFlowToInitial();
    }
    // Place/replace marker
    if (this.stopMarkers[index]) {
      this.stopMarkers[index].remove();
      this.stopMarkers[index] = null;
    }
    const marker = new maplibregl.Marker({ color: 'orange' }).setLngLat(coords).addTo(this.map);
    this.stopMarkers[index] = marker;
    this.stopCoords[index] = coords;
  }

  removeStop(index) {
    if (this.activeTab === 'offer' && this.offerConfirmed) {
      this.resetOfferFlowToInitial();
    }
    // Remove UI row
    const row = this.shadowRoot.querySelector(`.stop-row[data-index="${index}"]`);
    if (row) row.remove();
    // Remove marker/coords
    if (this.stopMarkers[index]) {
      this.stopMarkers[index].remove();
      this.stopMarkers[index] = null;
    }
    this.stopCoords[index] = undefined;
  }
  
  // Sauvegarde l'état des champs de l'onglet actuel
  saveTabFormState() {
    const fromEl = this.shadowRoot.getElementById('from');
    const toEl = this.shadowRoot.getElementById('to');
    const seatsEl = this.shadowRoot.getElementById('seats');
    
    if (this.activeTab === 'find') {
      const dateFindEl = this.shadowRoot.getElementById('date-find');
      this.tabFormState.find = {
        from: fromEl ? fromEl.value : '',
        to: toEl ? toEl.value : '',
        date: dateFindEl ? dateFindEl.value : '',
        returnDate: this.shadowRoot.getElementById('return-date-find')?.value || '',
        seats: seatsEl ? seatsEl.value : '4'
      };
    } else if (this.activeTab === 'offer') {
      const dateEl = this.shadowRoot.getElementById('date');
      const seatsReturnEl = this.shadowRoot.getElementById('seats-return');
      // Sauvegarder l'état complet, y compris les valeurs preset
      this.tabFormState.offer = {
        from: fromEl ? fromEl.value : '',
        to: toEl ? toEl.value : '',
        date: dateEl ? dateEl.value : '',
        fromTime: this.shadowRoot.getElementById('from-time')?.value || '00:00',
        seats: seatsEl ? seatsEl.value : '4',
        seatsReturn: seatsReturnEl ? seatsReturnEl.value : '4'
      };
    }
  }
  
  // Sauvegarde l'état initial de l'onglet "offer" après le preset
  saveInitialOfferState() {
    const fromEl = this.shadowRoot.getElementById('from');
    const toEl = this.shadowRoot.getElementById('to');
    const dateEl = this.shadowRoot.getElementById('date');
    const seatsEl = this.shadowRoot.getElementById('seats');
    const fromTimeEl = this.shadowRoot.getElementById('from-time');
    const seatsReturnEl = this.shadowRoot.getElementById('seats-return');
    
    this.tabFormState.offer = {
      from: fromEl ? fromEl.value : '',
      to: toEl ? toEl.value : '',
      date: dateEl ? dateEl.value : '',
      fromTime: fromTimeEl ? fromTimeEl.value : '00:00',
      seats: seatsEl ? seatsEl.value : '4',
      seatsReturn: seatsReturnEl ? seatsReturnEl.value : '4'
    };
    
    // Sauvegarder aussi l'état de la carte (marqueur du stade, etc.)
    if (this.endCoords) {
      this.tabMapState.offer.endCoords = [...this.endCoords];
      this.tabMapState.offer.endMarker = this.endMarker;
    }
    if (this.stadiumCoords) {
      this.tabMapState.offer.stadiumCoords = [...this.stadiumCoords];
    }
  }
  
  // Sauvegarde l'état de la carte de l'onglet actuel
  saveTabMapState() {
    const tab = this.activeTab;
    if (tab !== 'find' && tab !== 'offer' && tab !== 'mine') return;

    this.tabMapState[tab] = {
      startCoords: this.startCoords ? [...this.startCoords] : null,
      endCoords: this.endCoords ? [...this.endCoords] : null,
      startMarker: this.startMarker,
      endMarker: this.endMarker,
      stopCoords: this.stopCoords.map(c => c ? [...c] : null),
      stopMarkers: [...this.stopMarkers],
      stadiumCoords: this.stadiumCoords ? [...this.stadiumCoords] : null
    };
  }
  
  // Restaure l'état de la carte pour l'onglet ciblé
  restoreTabMapState(targetTab) {
    if (targetTab !== 'find' && targetTab !== 'offer' && targetTab !== 'mine') return;
    
    const state = this.tabMapState[targetTab];
    
    // ❗ NETTOYER COMPLÈTEMENT LA CARTE avant de restaurer
    if (this.map) {
      // Supprimer TOUS les layers et sources
      const layersToRemove = [
        this.routeLayerId, 'return-route-line', 'selected-offer-route-line',
        'search-radius-fill', 'search-radius', 'search-radius-outline', 
        'destination-radius-layer', 'destination-radius-outline-layer', 
        'offer-routes'
      ];
      const sourcesToRemove = [
        'route', 'return-route', 'selected-offer-route',
        'search-radius', 'destination-radius', 'offer-routes'
      ];
      
      layersToRemove.forEach(layerId => {
        if (this.map.getLayer(layerId)) {
          try { this.map.removeLayer(layerId); } catch(_) {}
        }
      });
      
      sourcesToRemove.forEach(sourceId => {
        if (this.map.getSource(sourceId)) {
          try { this.map.removeSource(sourceId); } catch(_) {}
        }
      });
    }
    
    // Nettoyer les marqueurs actuels
    if (this.startMarker && this.startMarker !== state.startMarker) {
      try { this.startMarker.remove(); } catch(_) {}
    }
    if (this.endMarker && this.endMarker !== state.endMarker) {
      try { this.endMarker.remove(); } catch(_) {}
    }
    this.stopMarkers.forEach((m, i) => {
      if (m && m !== state.stopMarkers[i]) {
        try { m.remove(); } catch(_) {}
      }
    });
    
    // Restaurer les coordonnées et marqueurs
    this.startCoords = state.startCoords ? [...state.startCoords] : null;
    this.endCoords = state.endCoords ? [...state.endCoords] : null;
    this.stadiumCoords = state.stadiumCoords ? [...state.stadiumCoords] : null;
    this.startMarker = state.startMarker;
    this.endMarker = state.endMarker;
    this.stopCoords = state.stopCoords.map(c => c ? [...c] : null);
    this.stopMarkers = [...state.stopMarkers];
    
    // Nettoyer les routes précédentes
    try {
      if (this.map) {
        // Route principale
        if (this.map.getSource('route')) {
          if (this.map.getLayer(this.routeLayerId)) {
            this.map.removeLayer(this.routeLayerId);
          }
          this.map.removeSource('route');
        }
        // Route retour
        if (this.map.getSource('return-route')) {
          if (this.map.getLayer('return-route-line')) {
            this.map.removeLayer('return-route-line');
          }
          this.map.removeSource('return-route');
        }
        // Route d'offre sélectionnée
        if (this.map.getSource('selected-offer-route')) {
          if (this.map.getLayer('selected-offer-route-line')) {
            this.map.removeLayer('selected-offer-route-line');
          }
          this.map.removeSource('selected-offer-route');
        }
      }
    } catch(_) {}
    
    // Réafficher les marqueurs restaurés sur la carte
    if (this.map) {
      if (this.startMarker) {
        try { this.startMarker.addTo(this.map); } catch(_) {}
      }
      if (this.endMarker) {
        try { this.endMarker.addTo(this.map); } catch(_) {}
      }
      this.stopMarkers.forEach(m => {
        if (m) {
          try { m.addTo(this.map); } catch(_) {}
        }
      });
    }
    
    // Ajuster la vue de la carte
    this.fitMapToBounds();
  }
  
  // Restaure l'état des champs pour l'onglet ciblé
  restoreTabFormState(targetTab) {
    const fromEl = this.shadowRoot.getElementById('from');
    const toEl = this.shadowRoot.getElementById('to');
    const seatsEl = this.shadowRoot.getElementById('seats');
    
    if (targetTab === 'find') {
      const state = this.tabFormState.find;
      const dateFindEl = this.shadowRoot.getElementById('date-find');
      const retDateEl = this.shadowRoot.getElementById('return-date-find');
      
      if (fromEl) fromEl.value = state.from || '';
      if (toEl) toEl.value = state.to || '';
      if (dateFindEl) dateFindEl.value = state.date || '';
      if (retDateEl) retDateEl.value = state.returnDate || '';
      if (seatsEl) seatsEl.value = state.seats || '4';
    } else if (targetTab === 'offer') {
      const state = this.tabFormState.offer;
      const dateEl = this.shadowRoot.getElementById('date');
      const fromTimeEl = this.shadowRoot.getElementById('from-time');
      const seatsReturnEl = this.shadowRoot.getElementById('seats-return');
      
      // Restaurer toujours les valeurs sauvegardées
      // Si aucune valeur n'a été saisie, les champs seront vidés
      // Les valeurs preset (stade, date) sont dans l'état sauvegardé
      if (fromEl) fromEl.value = state.from || '';
      if (toEl) toEl.value = state.to || '';
      if (dateEl) dateEl.value = state.date || '';
      if (seatsEl) seatsEl.value = state.seats || '4';
      if (fromTimeEl) fromTimeEl.value = state.fromTime || '00:00';
      if (seatsReturnEl) seatsReturnEl.value = state.seatsReturn || '4';
    }
  }
  
  async updateTabUI() {
    const tabFind = this.shadowRoot.getElementById("tab-find");
    const tabOffer = this.shadowRoot.getElementById("tab-offer");
    if (!tabFind || !tabOffer) return;
  const isFind = this.activeTab === 'find';
  const isOffer = this.activeTab === 'offer';
  const isMine = this.activeTab === 'mine';
    tabFind.classList.toggle('active', isFind);
  tabOffer.classList.toggle('active', isOffer);
  const tabMine = this.shadowRoot.getElementById('tab-mine');
  if (tabMine) tabMine.classList.toggle('active', isMine);
  tabFind.setAttribute('aria-selected', String(isFind));
  tabOffer.setAttribute('aria-selected', String(isOffer));
  if (tabMine) tabMine.setAttribute('aria-selected', String(isMine));
  // Ajuste le libellé du bouton principal (Rechercher vs Valider)
  const primaryBtn = this.shadowRoot.getElementById('validate');
  if (primaryBtn) primaryBtn.textContent = isFind ? 'Rechercher' : 'Valider';
  // En entrant sur l'onglet Trouver, désactive le filtrage jusqu'au clic Rechercher
  if (isFind) this.findFilterActive = false;
    // Affiche/masque les sections "offre uniquement" (UNIQUEMENT onglet Offer)
    this.shadowRoot.querySelectorAll('.offer-only').forEach(el => {
      const id = el.id;
      let shouldBeVisible = isOffer;
      if (isOffer) {
        // état initial Offer : seul confirm-trip-wrapper affiché
        if (id === 'calculate-btn-wrapper' || id === 'trip-summary' || id === 'map-box-container' || id === 'map-legend') {
          shouldBeVisible = false;
        }
        if (id === 'confirm-trip-wrapper') shouldBeVisible = true;
      }
      el.classList.toggle('visible', shouldBeVisible);
      if (!shouldBeVisible) {
        el.setAttribute('hidden','');
        el.style.display = 'none';
      } else {
        el.removeAttribute('hidden');
        el.style.removeProperty('display');
      }
    });
    
    // FORCER la visibilité correcte en mode Offer pour les éléments spéciaux
    if (isOffer) {
      const calculateWrapper = this.shadowRoot.getElementById('calculate-btn-wrapper');
      const tripSummary = this.shadowRoot.getElementById('trip-summary');
      const confirmWrapper = this.shadowRoot.getElementById('confirm-trip-wrapper');
      const mapBox = this.shadowRoot.getElementById('map-box-container');
      const legend = this.shadowRoot.getElementById('map-legend');
      
      // Réinitialiser à l'état initial : cacher carte, légende, calculer, récapitulatif
      this.offerConfirmed = false;
      this.setOfferStep(1);
    }
    
    // En mode Find, s'assurer que les champs de saisie sont visibles
    if (isFind) {
      const searchCard = this.shadowRoot.querySelector('.search-card');
      if (searchCard) {
        searchCard.style.removeProperty('display');
        searchCard.classList.remove('hidden');
      }
      // Masquer les éléments du wizard Offer
      const wizardBar = this.shadowRoot.getElementById('offer-wizard-bar');
      if (wizardBar) wizardBar.style.display = 'none';
      const routeSelectionWrapper = this.shadowRoot.getElementById('route-selection-wrapper');
      if (routeSelectionWrapper) routeSelectionWrapper.style.display = 'none';
    }
    // find-only visibles seulement sur find
    this.shadowRoot.querySelectorAll('.find-only').forEach(el => {
      const show = isFind;
      if (show) {
        el.removeAttribute('hidden');
        // Respect explicit display control for managed panels (loading/results)
        if (!el.classList.contains('keep-display')) {
          el.style.removeProperty('display');
        }
      } else {
        el.setAttribute('hidden','');
        el.style.display = 'none';
      }
    });
    // mine-only visibles seulement sur mine
    this.shadowRoot.querySelectorAll('.mine-only').forEach(el => {
      const show = isMine;
      if (show) { el.removeAttribute('hidden'); el.style.removeProperty('display'); }
      else { el.setAttribute('hidden',''); el.style.display = 'none'; }
    });

    // En mode "Mes trajets", masquer le formulaire, la meta-row, la carte et la légende
    const formEl = this.shadowRoot.querySelector('.form');
    const metaRow = this.shadowRoot.querySelector('.meta-row');
    const mapBox = this.shadowRoot.getElementById('map-box-container');
    const legend = this.shadowRoot.getElementById('map-legend');
    if (isMine) {
      if (formEl) formEl.style.display = 'none';
      if (metaRow) metaRow.style.display = 'none';
      if (mapBox) mapBox.style.display = 'none';
      if (legend) legend.style.display = 'none';
      // Nettoyer tout tracé de carte existant
      try {
        if (this.map) {
          if (this.map.getSource('selected-offer-route')) { if (this.map.getLayer('selected-offer-route-line')) this.map.removeLayer('selected-offer-route-line'); this.map.removeSource('selected-offer-route'); }
          if (this.map.getSource('route')) { if (this.map.getLayer(this.routeLayerId)) this.map.removeLayer(this.routeLayerId); this.map.removeSource('route'); }
          if (this.map.getSource('return-route')) { if (this.map.getLayer('return-route-line')) this.map.removeLayer('return-route-line'); this.map.removeSource('return-route'); }
        }
      } catch(_) {}
    } else {
      // Ré-afficher les éléments (ils seront ensuite masqués par leurs classes si besoin)
      if (formEl) formEl.style.removeProperty('display');
      if (metaRow) metaRow.style.removeProperty('display');
      
      // En mode "Proposer", cacher la carte et la légende initialement
      // Elles seront affichées uniquement après confirmation du trajet
      if (isOffer) {
        if (mapBox) mapBox.style.display = 'none';
        if (legend) legend.style.display = 'none';
      } else {
        // En mode "Find", afficher la carte et la légende
        if (mapBox) {
          mapBox.style.removeProperty('display');
          mapBox.classList.add('visible');
        }
        if (legend) {
          legend.style.removeProperty('display');
          legend.classList.add('visible');
        }
      }
    }
    // Rafraîchit les prix par segment si on passe côté Offre
    if (isOffer) {
      try { this.updateSegmentPrices(); } catch(_) {}
    } else if (isFind) {
      // Côté "Trouver": on n'affiche que l'itinéraire de l'offre cliquée -> supprimer tout tracé manuel éventuel
      try {
        if (this.map) {
          if (this.map.getSource('route')) { if (this.map.getLayer(this.routeLayerId)) this.map.removeLayer(this.routeLayerId); this.map.removeSource('route'); }
          if (this.map.getSource('return-route')) { if (this.map.getLayer('return-route-line')) this.map.removeLayer('return-route-line'); this.map.removeSource('return-route'); }
        }
      } catch(_) {}
      // Les offres seront affichées uniquement après une recherche
      // (pas d'affichage automatique lors du changement d'onglet)
      // try { await this.fetchCarpoolOffers(); } catch(_) {}
    } else if (isMine) {
      try { await this.fetchMyTrips(); } catch(_) {}
    }
  }

  async searchAddress(query, datalist) {
  if (!query || query.length < 3) {
    return [];
  }
  try {
    // Utiliser le proxy backend pour éviter CORS
    const res = await fetch(`/api/geocode/search?q=${encodeURIComponent(query)}&limit=5`);
    const data = await res.json();
    
    if (data.source === 'ban') {
      // Format BAN du proxy
      const features = [];
      for (const item of data.features || []) {
        features.push({
          properties: {
            label: item.label,
            name: item.name,
            postcode: item.postcode,
            city: item.city,
            type: item.type,
            score: item.score
          },
          geometry: {
            coordinates: [item.lon, item.lat]
          }
        });
        // Alimenter le cache
        if (item.label && item.lon && item.lat) {
          this.featureCache.set(item.label, [item.lon, item.lat]);
        }
      }
      return features;
    } else if (data.source === 'nominatim') {
      // Format Nominatim du proxy
      const features = [];
      for (const item of data.features || []) {
        features.push({
          properties: {
            label: item.label || item.display_name,
            name: item.name,
            type: item.type
          },
          geometry: {
            coordinates: [item.lon, item.lat]
          }
        });
        // Alimenter le cache
        if (item.label && item.lon && item.lat) {
          this.featureCache.set(item.label, [item.lon, item.lat]);
        }
      }
      return features;
    }
    return [];
  } catch (error) {
    console.error('❌ searchAddress error:', error);
    return [];
  }
}

  isMobile() {
    try {
      return (window.matchMedia && window.matchMedia('(max-width: 768px)').matches) || /Mobi|Android/i.test(navigator.userAgent);
    } catch (_) { return false; }
  }

  renderSuggestionsBelow(inputEl, features, onSelect) {
    // Nettoie si pas de résultats
    if (!inputEl) return;
    // Ne pas scroller automatiquement - laisse l'utilisateur voir où il est
    // this.scrollAnchorToTop(inputEl);
    if (!features || !features.length) {
      if (this.currentSuggestionPanel) this.hideSuggestionsPanel(this.currentSuggestionPanel);
      return;
    }
    // Création du panneau dans le parent .search-field pour positionnement relatif
    let panel = this.currentSuggestionPanel;
    const parentField = inputEl.closest('.search-field');
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'suggestions';
      // Position absolue par rapport au .search-field parent
      panel.style.position = 'absolute';
      panel.style.left = '0';
      panel.style.right = '0';
      panel.style.top = '100%';
      panel.style.marginTop = '2px';
      panel.style.zIndex = '15000';
      if (parentField) {
        parentField.style.position = 'relative';
        parentField.appendChild(panel);
      } else {
        this.shadowRoot.appendChild(panel);
      }
      this.currentSuggestionPanel = panel;
    }
    panel.innerHTML = features.map((f, i) => `<div class="suggestion-item" data-idx="${i}">${f.properties.label}</div>`).join('');
    // Enregistre l'ancre (plus besoin de positionner manuellement)
    this.currentSuggestionAnchor = inputEl;
    // Plus besoin d'appeler positionSuggestionsPanel() car position:absolute gère tout
    const onClick = async (e) => {
      const item = e.target.closest('.suggestion-item');
      if (!item) return;
      const idx = parseInt(item.dataset.idx, 10);
      const f = features[idx];
      if (!f) return;
      onSelect && onSelect(f);
      this.hideSuggestionsPanel(panel);
    };
    panel.onclick = onClick;
    // Fermer en cliquant dehors (dans le shadowRoot)
    const outside = (e) => {
      const path = e.composedPath ? e.composedPath() : [e.target];
      const target = path[0];
      if (!panel.contains(target) && this.currentSuggestionAnchor && !this.currentSuggestionAnchor.contains(target)) {
        this.hideSuggestionsPanel(panel);
        this.shadowRoot.removeEventListener('click', outside, true);
      }
    };
    setTimeout(() => {
      this.shadowRoot.addEventListener('click', outside, true);
    }, 0);
  }

  hideSuggestionsPanel(panel) {
    try { panel && panel.remove(); } catch(_){}
    this.currentSuggestionPanel = null;
    this.currentSuggestionAnchor = null;
  }

  openTimePicker(selectId) {
    const selectEl = this.shadowRoot.getElementById(selectId);
    if (!selectEl) return;
    const parentField = selectEl.closest('.search-field');
    if (!parentField) return;
    const existing = parentField.querySelector('.time-picker-panel');
    if (existing) try { existing.remove(); } catch(_) {}
    const panel = document.createElement('div');
    panel.className = 'time-picker-panel';
    const current = selectEl.value || '08:00';
    const values = this.generateTimeValues();
    const grid = values.map(v => `<button class="time-btn" data-v="${v}">${v}</button>`).join('');
    panel.innerHTML = `
      <div class="time-actions">
        <button class="time-action" data-action="minus15">- 15 min</button>
        <button class="time-action" data-action="plus15">+ 15 min</button>
      </div>
      <div class="time-grid">${grid}</div>
      <input type="time" class="time-input" value="${current}" />
    `;
    parentField.style.position = 'relative';
    parentField.appendChild(panel);
    const close = () => { try { panel.remove(); } catch(_){} };
    const selectAndClose = (val) => {
      selectEl.value = val;
      const displayId = selectId === 'from-time' ? 'from-time-display' : 'return-time-display';
      const dispEl = this.shadowRoot.getElementById(displayId);
      if (dispEl) dispEl.textContent = val;
      selectEl.dispatchEvent(new Event('change', { bubbles: true }));
      close();
    };
    panel.addEventListener('click', (e) => {
      const btn = e.target.closest('.time-btn');
      if (btn) {
        const val = btn.getAttribute('data-v');
        if (val) selectAndClose(val);
        return;
      }
      const act = e.target.closest('.time-action');
      if (act) {
        const action = act.getAttribute('data-action');
        const [hStr, mStr] = (selectEl.value || current).split(':');
        let h = parseInt(hStr, 10) || 0;
        let m = parseInt(mStr, 10) || 0;
        if (action === 'minus15') m -= 15; else if (action === 'plus15') m += 15;
        while (m < 0) { m += 60; h -= 1; }
        while (m >= 60) { m -= 60; h += 1; }
        if (h < 0) h = 0; if (h > 23) h = 23;
        const val = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
        selectAndClose(val);
        return;
      }
    });
    const input = panel.querySelector('.time-input');
    if (input) {
      input.addEventListener('change', () => {
        const val = input.value;
        if (val && /^\d{2}:\d{2}$/.test(val)) selectAndClose(val);
      });
    }
    const outside = (e) => {
      const path = e.composedPath ? e.composedPath() : [e.target];
      const target = path[0];
      if (!panel.contains(target)) {
        close();
        this.shadowRoot.removeEventListener('click', outside, true);
      }
    };
    setTimeout(() => this.shadowRoot.addEventListener('click', outside, true), 0);
  }

  positionSuggestionsPanel() {
    const panel = this.currentSuggestionPanel;
    const anchor = this.currentSuggestionAnchor;
    if (!panel || !anchor) return;
    try {
      const rect = anchor.getBoundingClientRect();
      const gap = 4; // petit espace pour partir juste en dessous du champ
      const vv = window.visualViewport;
      const vOffTop = vv ? (vv.offsetTop || vv.pageTop || 0) : 0;
      const vOffLeft = vv ? (vv.offsetLeft || vv.pageLeft || 0) : 0;
      const vHeight = vv ? vv.height : window.innerHeight;
      const vWidth = vv ? vv.width : window.innerWidth;
      panel.style.left = `${rect.left + vOffLeft}px`;
      panel.style.top = `${rect.bottom + gap + vOffTop}px`;
      panel.style.width = `${rect.width}px`;
      // s'assurer qu'on ne dépasse pas trop l'écran
      const maxW = Math.min(vWidth - 8, rect.width);
      // ajuste la hauteur dispo sous le champ pour rester sous l'input
      const available = Math.max(120, vHeight - (rect.bottom + gap) - 12);
      panel.style.maxHeight = `${Math.min(260, available)}px`;
      panel.style.maxWidth = `${maxW}px`;
    } catch(_){}
  }

  scrollAnchorToTop(anchor) {
    if (!this.isMobile() || !anchor) return;
    try {
      const rect = anchor.getBoundingClientRect();
      // Hauteur du header fixe : 80px (top) + 46px (nav) + 100px (indicator) + 20px marge = 246px
      const offset = 246;
      const delta = rect.top - offset;
      // Scroll la fenêtre pour caler l'input visible sous le header
      window.scrollBy({ top: delta, behavior: 'smooth' });
    } catch(_) { /* noop */ }
  }
fitMapToBounds() {
  const coords = [];
  if (this.startCoords) coords.push(this.startCoords);
  if (Array.isArray(this.stopCoords)) {
    this.stopCoords.forEach(c => { if (c) coords.push(c); });
  }
  if (this.endCoords) coords.push(this.endCoords);

  if (coords.length === 0) return; // rien à ajuster

  // Si un seul point (par ex. seulement le stade), on centre avec un zoom de contexte
  if (coords.length === 1) {
    try {
      this.map && this.map.easeTo({ center: coords[0], zoom: 12, duration: 400 });
      return;
    } catch (_) { /* ignore and fallback below */ }
  }

  // Initialise les bounds avec le premier point pour éviter extend(null)
  const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
  for (let i = 1; i < coords.length; i++) bounds.extend(coords[i]);

  this.map.fitBounds(bounds, { padding: 60 });
}


  async geocodeAndPlacePin(address, type) {
  // En mode "offer", on exige une adresse précise
  const requirePrecise = (this.activeTab === 'offer');
  const coords = await this.geocodeAddress(address, requirePrecise);
  if (!coords) return;
  
  // Vérifier si c'est une erreur de précision
  if (coords.error === 'precise_required') {
    const fieldName = type === 'start' ? 'de départ' : 'd\'arrivée';
    alert(`Pour proposer un covoiturage, veuillez saisir une adresse ${fieldName} précise (numéro de rue ou point d'intérêt), pas seulement une ville.`);
    return;
  }

  // En mode Offer si déjà confirmé, repasse à l'état initial avant de placer un nouveau pin
  if (this.activeTab === 'offer' && this.offerConfirmed) {
    this.resetOfferFlowToInitial();
  }

  const marker = new maplibregl.Marker({ color: type === "start" ? "blue" : "green" })
    .setLngLat(coords)
    .addTo(this.map);

  if (type === "start") {
    if (this.startMarker) this.startMarker.remove();
    this.startMarker = marker;
    this.startCoords = coords;
  } else if (type === "end") {
    if (this.endMarker) this.endMarker.remove();
    this.endMarker = marker;
    this.endCoords = coords;
    // mettre à jour le rayon autour de la destination
    this.updateDestinationRadius(5000);
    // vérifie si la destination se trouve hors du rayon et notifie
    this.checkDestinationProximity(5000);
  }

  // ✅ En mode "Trouver", ne pas tracer de route à partir des champs; uniquement en mode "Offre"
  // ✅ En mode "Proposer", ne plus tracer automatiquement - le tracé se fait au clic sur "Calculer l'itinéraire"
  // (désactivé pour que l'utilisateur contrôle quand les calculs se font)
  /*
  if (this.startCoords && this.endCoords && this.activeTab !== 'find') {
    await this.drawRouteOSRM();
    // Si retour activé, dessine aussi le trajet retour
    const returnCheckbox = this.shadowRoot.getElementById("return");
    if (returnCheckbox && returnCheckbox.checked) {
      const returnFrom = this.shadowRoot.getElementById("to").value;
      const returnTo = this.shadowRoot.getElementById("from").value;
      const start = await this.geocodeAddress(returnFrom);
      const end = await this.geocodeAddress(returnTo);
      if (start && end) {
        const returnViaStops = this.shadowRoot.getElementById('return-via-stops');
        const via = (returnViaStops && returnViaStops.checked) ? this.stopCoords.filter(Boolean).slice().reverse() : [];
        await this.drawReturnRouteOSRM(start, end, via);
      }
    }
  }
  */
  
  // Ajuste le cadre pour afficher tous les pins disponibles (seulement en mode "Trouver")
  if (this.activeTab === 'find') {
    this.fitMapToBounds();
  }
}

  async setCoordsAndMarkers(type, coords) {
    if (!Array.isArray(coords) || coords.length !== 2) return;
    // Si on est en mode Offer et que le flux a déjà été confirmé, repasse à l'état initial
    if (this.activeTab === 'offer' && this.offerConfirmed) {
      this.resetOfferFlowToInitial();
    }
    const marker = new maplibregl.Marker({ color: type === "start" ? "blue" : "green" })
      .setLngLat(coords)
      .addTo(this.map);

    if (type === "start") {
      if (this.startMarker) this.startMarker.remove();
      this.startMarker = marker;
      this.startCoords = coords;
    } else if (type === "end") {
      if (this.endMarker) this.endMarker.remove();
      this.endMarker = marker;
      this.endCoords = coords;
      // mettre à jour le rayon autour de la destination
      this.updateDestinationRadius(5000);
      // vérifie si la destination se trouve hors du rayon et notifie
      this.checkDestinationProximity(5000);
    }

    // Ne trace pas de route automatiquement en mode Offer; en mode Find, ajuster la vue
    if (this.activeTab === 'find') {
      this.fitMapToBounds();
    }
  }


  drawRoute() {
  if (!this.startCoords || !this.endCoords) return;

  // Supprime la source/layer s'ils existent déjà
  if (this.map.getSource("route")) {
    if (this.map.getLayer(this.routeLayerId)) {
      this.map.removeLayer(this.routeLayerId);
    }
    this.map.removeSource("route");
  }

  this.map.addSource("route", {
    type: "geojson",
    data: {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [this.startCoords, this.endCoords]
      }
    }
  });

  this.map.addLayer({
    id: this.routeLayerId,
    type: "line",
    source: "route",
    paint: {
      "line-color": "#229613",
      "line-width": 4
    }
  });
  // Cette fonction n'est plus utilisée, remplacée par drawRouteOSRM
}

  async checkAddressPrecision(address) {
    // Vérifie si une adresse est précise (pas juste une ville)
    if (!address) return { isPrecise: false };
    
    try {
      const banRes = await fetch(`https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(address)}&limit=1`);
      const banData = await banRes.json();
      if (banData.features && banData.features.length > 0) {
        const feature = banData.features[0];
        const type = feature.properties.type;
        const label = (feature.properties.label || '').toLowerCase();
        
        // Accepter explicitement les stades et points d'intérêt connus
        const isKnownPOI = label.includes('stade') || 
                          label.includes('stadium') || 
                          label.includes('bollaert') ||
                          label.includes('gare') ||
                          label.includes('aéroport') ||
                          label.includes('centre commercial') ||
                          label.includes('hôpital') ||
                          label.includes('université');
        
        // Types acceptés : housenumber, street, poi (et les POI connus même s'ils ont un autre type)
        // Types refusés : municipality, locality (sauf si c'est un POI connu)
        const isPrecise = (type !== 'municipality' && type !== 'locality') || isKnownPOI;
        
        return { isPrecise, type, label };
      }
    } catch(e) {
      console.warn('BAN check failed', e);
    }
    
    // Si on ne peut pas vérifier, on accepte par défaut
    return { isPrecise: true };
  }

  async geocodeAddress(address, requirePrecise = false) {
    if (!address) return null;
    
    // Utiliser le proxy backend pour éviter CORS
    try {
      const res = await fetch(`/api/geocode/search?q=${encodeURIComponent(address)}&limit=1`);
      const data = await res.json();
      
      if (data.source === 'ban' && data.features && data.features.length > 0) {
        const feature = data.features[0];
        const type = feature.type;
        const coords = [feature.lon, feature.lat];
        const label = (feature.label || '').toLowerCase();
        
        // Si on requiert une adresse précise (mode "offer")
        if (requirePrecise) {
          // Accepter explicitement les stades et points d'intérêt connus
          const isKnownPOI = label.includes('stade') || 
                            label.includes('stadium') || 
                            label.includes('bollaert') ||
                            label.includes('gare') ||
                            label.includes('aéroport') ||
                            label.includes('centre commercial') ||
                            label.includes('hôpital') ||
                            label.includes('université');
          
          // Types acceptés : housenumber (numéro de rue), street (rue), poi (point d'intérêt)
          // Types refusés : municipality (ville), locality (lieu-dit vague) SAUF si POI connu
          if ((type === 'municipality' || type === 'locality') && !isKnownPOI) {
            return { error: 'precise_required', type };
          }
        }
        
        return coords;
      } else if (data.source === 'nominatim' && data.features && data.features.length > 0) {
        const feature = data.features[0];
        return [feature.lon, feature.lat];
      }
      
      return null;
    } catch(e) {
      console.error('Geocoding failed:', e);
      return null;
    }
  }

  async drawReturnRouteOSRM(startCoords, endCoords, viaCoords = []) {
    this.setMapLoading(true);
    try {
    // Supprime la source/layer retour s'ils existent déjà
    if (this.map.getSource("return-route")) {
      if (this.map.getLayer("return-route-line")) {
        this.map.removeLayer("return-route-line");
      }
      this.map.removeSource("return-route");
    }
    // Construit la chaîne de coordonnées retour: départ = adresse d'arrivée, via = étapes inversées, arrivée = adresse de départ
    const coordsList = [ startCoords, ...(Array.isArray(viaCoords) ? viaCoords : []), endCoords ];
    const coordStr = coordsList.map(c => `${c[0]},${c[1]}`).join(';');
    // Appel OSRM pour le trajet retour (avec étapes si fournies)
    const url = `https://router.project-osrm.org/route/v1/driving/${coordStr}?overview=full&geometries=geojson`;
    const res = await fetch(url);
    const data = await res.json();
    if (!data.routes || !data.routes.length) return;
    try {
      this.lastReturnRouteDistanceMeters = data.routes[0].distance;
      // Stocker les données du trajet retour pour timeline et récap
      this.returnRoute = {
        distance: data.routes[0].distance,
        duration: data.routes[0].duration
      };
      this.retLegs = Array.isArray(data.routes[0].legs) ? data.routes[0].legs : [];
      this.returnStops = Array.isArray(viaCoords) ? viaCoords.slice() : [];
      this.updateSegmentPrices();
    } catch(_) {}
    const routeGeojson = {
      type: "Feature",
      geometry: data.routes[0].geometry
    };
    this.map.addSource("return-route", {
      type: "geojson",
      data: routeGeojson
    });
    this.map.addLayer({
      id: "return-route-line",
      type: "line",
      source: "return-route",
      paint: {
        "line-color": this.colorReturn,
        "line-width": 4,
        "line-dasharray": [2, 4]
      }
    });
    } finally {
      this.setMapLoading(false);
    }
  }

  // Nouvelle fonction : récupère plusieurs itinéraires alternatifs d'OSRM
  async fetchRouteAlternatives() {
    if (!this.startCoords || !this.endCoords) {
      console.warn('fetchRouteAlternatives: missing start or end coords');
      return [];
    }

    this.setMapLoading(true);
    try {
      const alternatives = [];
      
      // Utiliser le backend comme proxy pour éviter CORS
      console.log('🚗 Fetching route alternatives via backend...');
      
      const waypoints = [this.startCoords, this.endCoords];
      const backendRes = await fetch('/api/carpool/calculate-route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ waypoints, alternatives: true })
      });
      
      if (!backendRes.ok) {
        console.error('❌ Backend route calculation failed:', backendRes.status);
        return [];
      }
      
      const osrmData = await backendRes.json();
      
      console.log('📦 Backend response keys:', Object.keys(osrmData));
      
      if (osrmData.error) {
        console.error('❌ Backend error:', osrmData.error);
        return [];
      }
      
      // Le backend peut retourner:
      // - {routes: [...]} si OSRM avec alternatives
      // - {geometry, duration, distance, ...} si fallback Valhalla (pas d'alternatives)
      let routes = [];
      if (osrmData.routes && Array.isArray(osrmData.routes)) {
        routes = osrmData.routes;
        console.log(`✅ Backend returned ${routes.length} route alternative(s)`);
      } else if (osrmData.geometry) {
        // Format Valhalla : une seule route
        routes = [osrmData];
        console.log('✅ Backend returned 1 route (fallback Valhalla)');
      } else {
        console.warn('⚠️ Backend returned unexpected format');
        return [];
      }

      // En mode RSE : ne garder que la première route (la plus rapide)
      const isRSE = this.isRseMode();
      if (isRSE && routes.length > 1) {
        console.log('ℹ️ Mode RSE : une seule route sera affichée');
        routes = [routes[0]];
      }

      // Traiter les routes
      for (let index = 0; index < routes.length; index++) {
        const route = routes[index];
        console.log(`\n=== OSRM ROUTE ${index + 1} ===`);
        console.log('Distance:', route.distance, 'meters');
        console.log('Duration:', route.duration, 'seconds');
        
        const waypoints = await this.extractWaypointsFromRoute(route);
        const hasTolls = this.detectTolls(route);
        
        console.log(`>>> RESULT: hasTolls=${hasTolls}, distance=${(route.distance/1000).toFixed(1)}km, waypoints:`, waypoints);
        
        alternatives.push({
          id: alternatives.length,
          index: alternatives.length,
          distance: route.distance,
          duration: route.duration,
          geometry: route.geometry,
          legs: route.legs || [],
          waypoints: waypoints,
          hasTolls: hasTolls
        });
      }

      // 2. Ajouter systématiquement un itinéraire sans autoroute via OpenRouteService
      // si on a moins de 2 routes OU si aucune route sans péage
      // MAIS: sauter cette étape en mode RSE (on ne veut qu'une seule route)
      const hasFreeTollRoute = alternatives.some(alt => !alt.hasTolls);
      
      if (!isRSE && (alternatives.length < 2 || !hasFreeTollRoute) && this.openRouteServiceApiKey) {
        console.log('🛣️ Ajout d\'un itinéraire sans autoroute via OpenRouteService...');
        
        try {
          const orsUrl = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson';
          
          const orsBody = {
            coordinates: [
              [this.startCoords[0], this.startCoords[1]],
              [this.endCoords[0], this.endCoords[1]]
            ],
            options: {
              avoid_features: ['tollways', 'highways']
            },
            instructions: true
          };
          
          const orsRes = await fetch(orsUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json, application/geo+json',
              'Authorization': this.openRouteServiceApiKey
            },
            body: JSON.stringify(orsBody)
          });
          
          if (orsRes.ok) {
            const orsData = await orsRes.json();
            
            if (orsData.features && orsData.features.length > 0) {
              const orsRoute = orsData.features[0];
              const props = orsRoute.properties;
              const segments = props.segments || [];
              
              console.log('\n=== ROUTE SANS PÉAGE (via OpenRouteService) ===');
              console.log('Distance:', props.summary?.distance, 'meters');
              console.log('Duration:', props.summary?.duration, 'seconds');
              
              const geometry = orsRoute.geometry;
              
              // Pour ORS, il faut ajouter la durée au niveau du leg
              const noTollRoute = {
                distance: props.summary?.distance || 0,
                duration: props.summary?.duration || 0,
                geometry: geometry,
                legs: segments.map(seg => {
                  const segmentDuration = (seg.steps || []).reduce((sum, step) => sum + (step.duration || 0), 0);
                  return {
                    duration: segmentDuration,
                    distance: seg.distance || 0,
                    steps: seg.steps?.map(step => ({
                      name: step.name || '',
                      distance: step.distance || 0,
                      duration: step.duration || 0
                    })) || []
                  };
                })
              };
              
              const waypoints = await this.extractWaypointsFromRoute(noTollRoute);
              
              alternatives.push({
                id: alternatives.length,
                index: alternatives.length,
                distance: noTollRoute.distance,
                duration: noTollRoute.duration,
                geometry: geometry,
                legs: noTollRoute.legs,
                waypoints: waypoints,
                hasTolls: false,
                noTollRoute: true
              });
              
              console.log('✅ Itinéraire sans péage ajouté (garanti 0€)');
            }
          } else {
            const errorText = await orsRes.text();
            console.log('⚠️ OpenRouteService erreur:', orsRes.status, errorText);
          }
        } catch (orsError) {
          console.warn('OpenRouteService tentative échouée:', orsError.message);
        }
      } else if (!isRSE && (alternatives.length < 2 || !hasFreeTollRoute) && !this.openRouteServiceApiKey) {
        console.log('💡 Pour activer un itinéraire sans autoroute, ajoutez: <carpool-widget ors-api-key="VOTRE_CLE"></carpool-widget>');
        console.log('   Clé gratuite sur https://openrouteservice.org/dev/#/signup (2000 req/jour)');
      }
      
      // 3. Détecter et supprimer les doublons (même géométrie avec détection de péage différente)
      const uniqueAlternatives = [];
      for (const alt of alternatives) {
        const coordsStr = JSON.stringify(alt.geometry.coordinates);
        const isDuplicate = uniqueAlternatives.some(existing => {
          const existingCoordsStr = JSON.stringify(existing.geometry.coordinates);
          // Si les géométries sont très similaires (± 1% de différence de distance)
          const distDiff = Math.abs(existing.distance - alt.distance);
          const isSimilarDistance = distDiff < (alt.distance * 0.01);
          return existingCoordsStr === coordsStr || (isSimilarDistance && distDiff < 500);
        });
        
        if (!isDuplicate) {
          uniqueAlternatives.push(alt);
        } else {
          console.log(`⚠️ Duplicate route detected and removed (${(alt.distance/1000).toFixed(1)}km)`);
        }
      }
      
      console.log(`ℹ️ ${uniqueAlternatives.length} itinéraire(s) trouvé(s) (${alternatives.length - uniqueAlternatives.length} doublons supprimés)`);

      return uniqueAlternatives;
    } catch (error) {
      console.error('fetchRouteAlternatives error:', error);
      return [];
    } finally {
      this.setMapLoading(false);
    }
  }

  // Récupère les alternatives pour le trajet RETOUR (sens inverse)
  async fetchReturnRouteAlternatives() {
    if (!this.startCoords || !this.endCoords) {
      console.warn('fetchReturnRouteAlternatives: missing coords');
      return [];
    }

    this.setMapLoading(true);
    try {
      const alternatives = [];
      
      // Utiliser le backend avec coordonnées inversées (endCoords -> startCoords)
      console.log('🔄 Fetching RETURN route alternatives via backend...');
      
      const waypoints = [this.endCoords, this.startCoords];
      const backendRes = await fetch('/api/carpool/calculate-route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ waypoints, alternatives: true })
      });
      
      if (!backendRes.ok) {
        console.error('❌ Backend route calculation failed (return):', backendRes.status);
        return [];
      }
      
      const osrmData = await backendRes.json();
      
      if (osrmData.error) {
        console.error('❌ Backend error (return):', osrmData.error);
        return [];
      }
      
      // Gérer les deux formats de réponse
      let routes = [];
      if (osrmData.routes && Array.isArray(osrmData.routes)) {
        routes = osrmData.routes;
      } else if (osrmData.geometry) {
        routes = [osrmData];
      } else {
        console.warn('⚠️ No return routes found');
        return [];
      }
      
      console.log(`✅ Backend returned ${routes.length} return route(s)`);

      // Traiter les routes pour le retour
      for (let index = 0; index < routes.length; index++) {
        const route = routes[index];
        console.log(`\n=== RETURN ROUTE ${index + 1} ===`);
        console.log('Distance:', route.distance, 'meters');
        console.log('Duration:', route.duration, 'seconds');
        console.log('Legs:', route.legs);
        
        const waypoints = await this.extractWaypointsFromRoute(route);
        const hasTolls = this.detectTolls(route);
        
        alternatives.push({
          id: alternatives.length,
          index: alternatives.length,
          distance: route.distance,
          duration: route.duration,
          geometry: route.geometry,
          legs: route.legs || [],
          waypoints: waypoints,
          hasTolls: hasTolls
        });
      }

      // Tenter d'ajouter un itinéraire sans autoroute si on a moins de 2 routes OU si aucune sans péage
      const hasFreeTollRoute = alternatives.some(alt => !alt.hasTolls);
      
      if ((alternatives.length < 2 || !hasFreeTollRoute) && this.openRouteServiceApiKey) {
        console.log('🛣️ Ajout d\'un itinéraire retour sans autoroute...');
        
        try {
          const orsUrl = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson';
          
          const orsBody = {
            coordinates: [
              [this.endCoords[0], this.endCoords[1]],
              [this.startCoords[0], this.startCoords[1]]
            ],
            options: {
              avoid_features: ['tollways', 'highways']
            },
            instructions: true
          };
          
          const orsRes = await fetch(orsUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json, application/geo+json',
              'Authorization': this.openRouteServiceApiKey
            },
            body: JSON.stringify(orsBody)
          });
          
          if (orsRes.ok) {
            const orsData = await orsRes.json();
            
            if (orsData.features && orsData.features.length > 0) {
              const orsRoute = orsData.features[0];
              const props = orsRoute.properties;
              const segments = props.segments || [];
              
              console.log('\n=== RETURN ROUTE SANS PÉAGE ===');
              console.log('Distance:', props.summary?.distance, 'meters');
              
              const geometry = orsRoute.geometry;
              
              // Pour ORS, il faut ajouter la durée au niveau du leg
              const noTollRoute = {
                distance: props.summary?.distance || 0,
                duration: props.summary?.duration || 0,
                geometry: geometry,
                legs: segments.map(seg => {
                  const segmentDuration = (seg.steps || []).reduce((sum, step) => sum + (step.duration || 0), 0);
                  return {
                    duration: segmentDuration,
                    distance: seg.distance || 0,
                    steps: seg.steps?.map(step => ({
                      name: step.name || '',
                      distance: step.distance || 0,
                      duration: step.duration || 0
                    })) || []
                  };
                })
              };
              
              const waypoints = await this.extractWaypointsFromRoute(noTollRoute);
              
              alternatives.push({
                id: alternatives.length,
                index: alternatives.length,
                distance: noTollRoute.distance,
                duration: noTollRoute.duration,
                geometry: geometry,
                legs: noTollRoute.legs,
                waypoints: waypoints,
                hasTolls: false,
                noTollRoute: true
              });
              
              console.log('✅ Itinéraire retour sans péage ajouté');
            }
          }
        } catch (orsError) {
          console.warn('OpenRouteService retour échoué:', orsError.message);
        }
      }
      
      // Détecter et supprimer les doublons (même géométrie)
      const uniqueAlternatives = [];
      for (const alt of alternatives) {
        const coordsStr = JSON.stringify(alt.geometry.coordinates);
        const isDuplicate = uniqueAlternatives.some(existing => {
          const existingCoordsStr = JSON.stringify(existing.geometry.coordinates);
          const distDiff = Math.abs(existing.distance - alt.distance);
          const isSimilarDistance = distDiff < (alt.distance * 0.01);
          return existingCoordsStr === coordsStr || (isSimilarDistance && distDiff < 500);
        });
        
        if (!isDuplicate) {
          uniqueAlternatives.push(alt);
        } else {
          console.log(`⚠️ Duplicate return route detected and removed (${(alt.distance/1000).toFixed(1)}km)`);
        }
      }
      
      console.log(`ℹ️ ${uniqueAlternatives.length} itinéraire(s) retour trouvé(s) (${alternatives.length - uniqueAlternatives.length} doublons supprimés)`);

      this.routeAlternativesReturn = uniqueAlternatives;
      
      // Afficher les alternatives retour sur la carte
      await this.displayReturnRouteAlternatives();
      
      // Générer le HTML des cartes
      const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
      if (routeListEl) {
        routeListEl.innerHTML = this.renderRouteAlternativesHTMLForReturn();
        this.attachReturnRouteAlternativeListeners();
      }

      this.fitMapToAllAlternatives(true); // true = mode retour

      return alternatives;
    } catch (error) {
      console.error('fetchReturnRouteAlternatives error:', error);
      return [];
    } finally {
      this.setMapLoading(false);
    }
  }

  // Affiche les alternatives RETOUR sur la carte
  async displayReturnRouteAlternatives() {
    if (!this.routeAlternativesReturn || this.routeAlternativesReturn.length === 0) {
      console.warn('No return route alternatives to display');
      return;
    }

    try {
      // Nettoyer les anciennes routes aller (principale + alternatives)
      if (this.map.getLayer(this.routeLayerId)) this.map.removeLayer(this.routeLayerId);
      if (this.map.getSource("route")) this.map.removeSource("route");
      
      if (this.routeAlternatives && this.routeAlternatives.length > 0) {
        this.routeAlternatives.forEach((alt) => {
          const layerId = `route-alt-${alt.id}`;
          const sourceId = `route-alt-${alt.id}`;
          if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
          if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
        });
      }

      // Afficher toutes les alternatives retour
      this.routeAlternativesReturn.forEach((alt, index) => {
        const layerId = `route-return-alt-${alt.id}`;
        const sourceId = `route-return-alt-${alt.id}`;

        // Supprimer si existe déjà
        if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
        if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);

        // Ajouter la source
        this.map.addSource(sourceId, {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: alt.geometry
          }
        });

        // Pas de présélection automatique - l'utilisateur doit choisir
        const isSelected = this.selectedRouteIndexReturn === index;

        // Ajouter le layer - toutes les routes en gris par défaut
        this.map.addLayer({
          id: layerId,
          type: "line",
          source: sourceId,
          paint: {
            "line-color": isSelected ? this.colorReturn : "#8E8E93",
            "line-width": isSelected ? 5 : 3,
            "line-opacity": isSelected ? 1 : 0.5
          }
        });
      });
    } catch (error) {
      console.error('Error displaying return route alternatives:', error);
    }
  }

  // Highlight (visualisation) d'un trajet alternatif RETOUR - gris foncé et plus large
  highlightReturnRouteAlternative(index) {
    if (!this.routeAlternativesReturn || index < 0 || index >= this.routeAlternativesReturn.length) {
      console.warn('highlightReturnRouteAlternative: invalid index', index);
      return;
    }

    console.log('Highlighting route RETOUR:', index);

    // Mettre à jour les lignes sur la carte - TOUS EN GRIS
    this.routeAlternativesReturn.forEach((alt, i) => {
      const layerId = `route-return-alt-${alt.id}`;
      if (this.map.getLayer(layerId)) {
        const isHighlighted = i === index;
        // Celui survolé : gris foncé et large (6px)
        // Les autres : gris clair et fin (3px)
        const color = '#8E8E93'; // Toujours gris
        const width = isHighlighted ? 6 : 3;
        const opacity = isHighlighted ? 1.0 : 0.4;
        
        this.map.setPaintProperty(layerId, 'line-color', color);
        this.map.setPaintProperty(layerId, 'line-width', width);
        this.map.setPaintProperty(layerId, 'line-opacity', opacity);
      }
    });
  }

  // Sélectionne une alternative RETOUR (bouton "Choisir")
  selectReturnRouteAlternative(index) {
    if (!this.routeAlternativesReturn || index < 0 || index >= this.routeAlternativesReturn.length) {
      console.warn('Invalid return route index:', index);
      return;
    }

    console.log('Route retour alternative sélectionnée:', index, this.routeAlternativesReturn[index]);
    this.selectedRouteIndexReturn = index;
    const selected = this.routeAlternativesReturn[index];

    // Mettre à jour les styles des cartes
    const cards = this.shadowRoot.querySelectorAll('.route-alternative-card');
    cards.forEach((card, idx) => {
      if (idx === index) {
        card.classList.add('selected');
      } else {
        card.classList.remove('selected');
      }
    });

    // Mettre à jour les badges
    const badges = this.shadowRoot.querySelectorAll('.route-badge');
    badges.forEach((badge, idx) => {
      badge.style.backgroundColor = (idx === index) ? this.colorReturn : '#8e8e93';
    });

    // Mettre à jour les couleurs sur la carte - colorReturn pour le sélectionné
    this.routeAlternativesReturn.forEach((alt, idx) => {
      const layerId = `route-return-alt-${alt.id}`;
      if (this.map.getLayer(layerId)) {
        const isSelected = idx === index;
        const color = isSelected ? this.colorReturn : '#8E8E93';
        this.map.setPaintProperty(layerId, 'line-color', color);
        this.map.setPaintProperty(layerId, 'line-width', isSelected ? 5 : 3);
        this.map.setPaintProperty(layerId, 'line-opacity', isSelected ? 1.0 : 0.5);
      }
    });

    // Stocker les données de la route retour sélectionnée
    this.returnRoute = {
      distance: selected.distance,
      duration: selected.duration,
      geometry: selected.geometry
    };
    this.retLegs = selected.legs || [];
    this.lastReturnRouteDistanceMeters = selected.distance;

    // Si la carte summary existe, mettre à jour les routes et buffers
    if (this.summaryMap) {
      this.displaySummaryRoutes();
      const checkbox = this.shadowRoot.getElementById('accept-intermediate-passengers');
      const timeSlider = this.shadowRoot.getElementById('detour-time-slider');
      if (checkbox?.checked && timeSlider) {
        const minutes = parseInt(timeSlider.value, 10);
        const avgSpeedKmH = 50;
        const bufferWidthKm = avgSpeedKmH * (minutes / 60) * 0.5;
        this.updateSummaryDetourBuffers(bufferWidthKm);
      }
    }

    console.log('✅ Route retour stockée - retLegs:', this.retLegs);
    console.log('✅ Route retour stockée - selected:', selected);
  }

  // Désélectionne le trajet retour
  deselectReturnRouteAlternative() {
    console.log('🔄 Désélection du trajet retour');
    this.selectedRouteIndexReturn = null;
    this.returnRoute = null;
    this.retLegs = [];
    this.lastReturnRouteDistanceMeters = null;

    // Mettre à jour le visuel des cartes
    const cards = this.shadowRoot.querySelectorAll('.route-alternative-card');
    cards.forEach((card) => {
      card.classList.remove('selected');
      const badge = card.querySelector('.route-badge');
      if (badge) badge.style.background = '#8e8e93';
      const btn = card.querySelector('.btn-select-route');
      if (btn) {
        btn.classList.remove('btn-cancel');
        btn.textContent = 'Choisir';
      }
    });

    // Remettre toutes les lignes en gris
    this.routeAlternativesReturn.forEach((alt) => {
      const layerId = `route-return-alt-${alt.id}`;
      if (this.map.getLayer(layerId)) {
        this.map.setPaintProperty(layerId, 'line-color', '#8E8E93');
        this.map.setPaintProperty(layerId, 'line-opacity', 0.5);
        this.map.setPaintProperty(layerId, 'line-width', 3);
      }
    });
  }

  // Passer de l'étape 3 (choix retour) à l'étape 4 (ajustements)
  async proceedToAdjustmentsFromReturn() {
    if (this.selectedRouteIndexReturn === null) {
      alert('Veuillez sélectionner un itinéraire retour');
      return;
    }

    const selected = this.routeAlternativesReturn[this.selectedRouteIndexReturn];
    if (!selected) {
      alert('Erreur : trajet retour non trouvé');
      return;
    }

    // Nettoyer les anciennes alternatives retour de la carte
    this.routeAlternativesReturn.forEach((alt) => {
      const layerId = `route-return-alt-${alt.id}`;
      const sourceId = `route-return-alt-${alt.id}`;
      if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
      if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
    });

    // Dessiner le trajet aller sélectionné en bleu
    const selectedAller = this.routeAlternatives[this.selectedRouteIndex];
    if (selectedAller) {
      if (this.map.getSource("route")) {
        if (this.map.getLayer(this.routeLayerId)) {
          this.map.removeLayer(this.routeLayerId);
        }
        this.map.removeSource("route");
      }

      this.map.addSource("route", {
        type: "geojson",
        data: {
          type: "Feature",
          geometry: selectedAller.geometry
        }
      });

      this.map.addLayer({
        id: this.routeLayerId,
        type: "line",
        source: "route",
        paint: {
          "line-color": this.colorOutbound,
          "line-width": 5
        }
      });
    }

    // Dessiner le trajet retour sélectionné en bleu pointillé
    if (this.map.getSource("return-route")) {
      if (this.map.getLayer("return-route-line")) {
        this.map.removeLayer("return-route-line");
      }
      this.map.removeSource("return-route");
    }

    this.map.addSource("return-route", {
      type: "geojson",
      data: {
        type: "Feature",
        geometry: selected.geometry
      }
    });

    this.map.addLayer({
      id: "return-route-line",
      type: "line",
      source: "return-route",
      paint: {
        "line-color": this.colorReturn,
        "line-width": 4,
        "line-dasharray": [2, 4]
      }
    });

    // Stocker les données du trajet retour
    this.returnRoute = {
      distance: selected.distance,
      duration: selected.duration
    };
    this.retLegs = selected.legs || [];
    this.lastReturnRouteDistanceMeters = selected.distance;

    // Préparer les timelines
    try { this.updateOutboundTimeline(); } catch(_) {}
    try { this.updateReturnTimeline(); } catch(_) {}
    try { this.updateSegmentPrices(); } catch(_) {}

    // Peupler le récapitulatif avant d'y aller (tous les modes)
    await this.populateTripSummary();
    
    // Passer à l'étape ajustements/récapitulatif
    this.setOfferStep(4);
  }

  // Génère le HTML pour les alternatives RETOUR
  renderRouteAlternativesHTMLForReturn() {
    const isDark = this.theme === 'dark';
    const textSecondary = isDark ? '#a0a0a0' : '#8e8e93';
    if (!this.routeAlternativesReturn || !this.routeAlternativesReturn.length) {
      return `<p style="color: ${textSecondary}; text-align: center; padding: 20px;">Aucun itinéraire retour trouvé</p>`;
    }

    return this.routeAlternativesReturn.map((alt, index) => {
      const isSelected = this.selectedRouteIndexReturn === index;
      
      const distanceKm = (alt.distance / 1000).toFixed(0);
      const durationHours = Math.floor(alt.duration / 3600);
      const durationMins = Math.round((alt.duration % 3600) / 60);
      const durationStr = durationHours > 0 
        ? `${durationHours}h${String(durationMins).padStart(2, '0')}`
        : `${durationMins} min`;

      let tollsStr = '0€';
      let routeLabel = `Trajet ${index + 1}`;
      
      if (alt.hasTolls) {
        const estimatedTolls = Math.round((alt.distance / 1000) * 0.10);
        tollsStr = `~${estimatedTolls}€`;
      } else if (alt.noTollRoute) {
        // Garder "Trajet X" au lieu de "Sans péage"
        tollsStr = '0€ ✓';
      }

      const viaStr = alt.waypoints && alt.waypoints.length 
        ? alt.waypoints.slice(0, 4).join(' • ')
        : 'Itinéraire direct';

      return `
        <div class="route-alternative-card return-route ${isSelected ? 'selected' : ''}" data-route-index="${index}">
          <div class="route-header">
            <div class="route-title">
              <span class="route-badge">${routeLabel}</span>
            </div>
            <div class="checkmark">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M20 6L9 17l-5-5" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
          <div class="route-meta">
            <div class="route-meta-item">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
                <path d="M12 6v6l4 2" stroke="currentColor" stroke-width="2"/>
              </svg>
              <strong>Durée:</strong>
              <span>${durationStr}</span>
            </div>
            <div class="route-meta-item">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 12h18M3 6h18M3 18h18" stroke="currentColor" stroke-width="2"/>
              </svg>
              <strong>Distance:</strong>
              <span>${distanceKm} km</span>
            </div>
            <div class="route-meta-item">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/>
                <path d="M3 9h18M9 3v18" stroke="currentColor" stroke-width="2"/>
              </svg>
              <strong>Péages:</strong>
              <span>${tollsStr}</span>
            </div>
          </div>
          <div class="route-via">
            <strong>Itinéraire</strong>
            ${viaStr}
          </div>
          <button class="btn-select-route ${isSelected ? 'btn-cancel' : ''}" data-route-index="${index}">
            ${isSelected ? 'Annuler la sélection' : 'Choisir'}
          </button>
        </div>
      `;
    }).join('');
  }

  // Extrait les villes/étapes principales d'une route OSRM
  async extractWaypointsFromRoute(route) {
    const waypoints = [];
    try {
      if (!route.legs || !Array.isArray(route.legs)) return waypoints;
      
      // Liste de grandes villes françaises à détecter dans les noms de steps
      const majorCities = [
        'Paris', 'Marseille', 'Lyon', 'Toulouse', 'Nice', 'Nantes', 'Montpellier', 
        'Strasbourg', 'Bordeaux', 'Lille', 'Rennes', 'Reims', 'Saint-Étienne', 
        'Toulon', 'Le Havre', 'Grenoble', 'Dijon', 'Angers', 'Nîmes', 'Villeurbanne',
        'Clermont-Ferrand', 'Le Mans', 'Aix-en-Provence', 'Brest', 'Tours', 'Amiens',
        'Limoges', 'Annecy', 'Perpignan', 'Boulogne-Billancourt', 'Metz', 'Besançon',
        'Orléans', 'Saint-Denis', 'Argenteuil', 'Rouen', 'Montreuil', 'Caen', 'Nancy',
        'Tourcoing', 'Roubaix', 'Nanterre', 'Vitry-sur-Seine', 'Avignon', 'Créteil',
        'Dunkerque', 'Poitiers', 'Asnières-sur-Seine', 'Versailles', 'Courbevoie',
        'Colombes', 'Aulnay-sous-Bois', 'Saint-Pierre', 'Rueil-Malmaison', 'Pau',
        'Aubervilliers', 'Champigny-sur-Marne', 'Antibes', 'La Rochelle', 'Calais',
        'Cannes', 'Béziers', 'Colmar', 'Quimper', 'Valence', 'Bourges', 'Mérignac',
        'Saint-Nazaire', 'Villejuif', 'Troyes', 'Arras', 'Lens', 'Douai', 'Béthune'
      ];
      
      const foundCities = new Set();
      
      // Parcourir tous les steps pour trouver des mentions de villes
      route.legs.forEach(leg => {
        if (!leg.steps || !Array.isArray(leg.steps)) return;
        
        leg.steps.forEach(step => {
          const name = step.name || '';
          
          // Chercher si le nom contient une grande ville
          majorCities.forEach(city => {
            // Recherche insensible à la casse et aux accents
            const regex = new RegExp(`\\b${city.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
            if (regex.test(name)) {
              foundCities.add(city);
            }
          });
        });
      });
      
      // Si on a trouvé des villes, les retourner
      if (foundCities.size > 0) {
        return Array.from(foundCities).slice(0, 4);
      }
      
      // Sinon, fallback sur le reverse geocoding de quelques points
      const coordinates = route.geometry?.coordinates || [];
      if (coordinates.length < 2) return waypoints;
      
      // Prendre 2-3 points intermédiaires seulement
      const numPoints = Math.min(3, Math.floor(coordinates.length / 3));
      const step = Math.floor(coordinates.length / (numPoints + 1));
      
      const cityPromises = [];
      for (let i = 1; i <= numPoints; i++) {
        const idx = i * step;
        if (idx >= 0 && idx < coordinates.length) {
          const [lng, lat] = coordinates[idx];
          cityPromises.push(
            fetch(`https://api-adresse.data.gouv.fr/reverse/?lon=${lng}&lat=${lat}`)
              .then(res => res.json())
              .then(data => {
                if (data.features && data.features.length > 0) {
                  const props = data.features[0].properties;
                  return props.city || props.municipality || props.village || props.name;
                }
                return null;
              })
              .catch(() => null)
          );
        }
      }
      
      const cities = await Promise.all(cityPromises);
      const validCities = cities.filter(c => c && c.length > 2);
      
      return [...new Set(validCities)];
    } catch (e) {
      console.warn('extractWaypointsFromRoute error:', e);
      return waypoints;
    }
  }

  // Détecte si le trajet emprunte des autoroutes (donc péages probables)
  detectTolls(route) {
    console.log('>>> detectTolls called with route:', { 
      hasLegs: !!route.legs, 
      legsCount: route.legs?.length,
      distance: route.distance,
      duration: route.duration
    });
    
    try {
      let hasHighwaySegment = false;
      let totalHighwayDistance = 0;
      
      // Stratégie 1 : Chercher dans les steps si disponibles
      if (route.legs && Array.isArray(route.legs)) {
        
        for (const leg of route.legs) {
          if (!leg.steps || !Array.isArray(leg.steps)) {
            console.log('>>> No steps in this leg');
            continue;
          }
          
          console.log(`>>> Checking ${leg.steps.length} steps...`);
          for (const step of leg.steps) {
            const name = step.name || '';
            const distance = step.distance || 0;
            
            // Détecter les autoroutes avec numéro spécifique (A1, A26, A21, etc.)
            const highwayMatch = name.match(/\bA\s?(\d+)\b/i);
            if (highwayMatch) {
              const highwayNumber = parseInt(highwayMatch[1]);
              hasHighwaySegment = true;
              totalHighwayDistance += distance;
              console.log(`>>> detectTolls: Highway segment detected: ${name} (${(distance/1000).toFixed(1)}km)`);
            }
          }
        }
      }
      
      // Si présence d'autoroute ET distance autoroutière significative (> 5km), 
      // considérer comme potentiellement payant
      if (hasHighwaySegment && totalHighwayDistance > 5000) {
        console.log(`>>> detectTolls: TOLL LIKELY (${(totalHighwayDistance/1000).toFixed(1)}km on highway)`);
        
        // Vérifier la vitesse moyenne pour confirmer
        if (route.distance && route.duration) {
          const distanceKm = route.distance / 1000;
          const durationHours = route.duration / 3600;
          const avgSpeed = distanceKm / durationHours;
          
          console.log(`>>> detectTolls: avgSpeed=${avgSpeed.toFixed(1)} km/h`);
          
          // Si vitesse moyenne > 90 km/h avec segments autoroute, c'est un péage
          if (avgSpeed > 90) {
            console.log('>>> detectTolls: TOLL CONFIRMED (highway + high speed)');
            return true;
          } else {
            console.log('>>> detectTolls: NO TOLL (highway present but low speed, likely urban/congested)');
          }
        } else {
          return true; // Par défaut, si autoroute sans info vitesse
        }
      }
      
      // Stratégie 2 : Heuristique vitesse moyenne seule (si pas de segments détectés)
      if (!hasHighwaySegment && route.distance && route.duration) {
        const distanceKm = route.distance / 1000;
        const durationHours = route.duration / 3600;
        const avgSpeed = distanceKm / durationHours;
        
        console.log(`>>> detectTolls: avgSpeed=${avgSpeed.toFixed(1)} km/h (distance=${distanceKm.toFixed(1)}km, duration=${durationHours.toFixed(2)}h)`);
        
        // Autoroute typique : 110-130 km/h
        // Seuil élevé pour éviter faux positifs
        if (avgSpeed > 100) {
          console.log('>>> detectTolls: TOLL DETECTED (very high speed > 100 km/h)');
          return true;
        } else {
          console.log('>>> detectTolls: NO TOLL (speed <= 100 km/h)');
        }
      }
      
    } catch (e) {
      console.warn('detectTolls error:', e);
    }
    
    console.log('>>> detectTolls: FINAL RESULT = NO TOLLS');
    return false;
  }

  // Affiche les alternatives de trajet sur la carte (étape 2)
  async displayRouteAlternatives() {
    if (!this.routeAlternatives || !this.routeAlternatives.length) {
      console.warn('displayRouteAlternatives: no alternatives to display');
      return;
    }

    // Nettoyer les anciennes routes retour si elles existent
    if (this.routeAlternativesReturn && this.routeAlternativesReturn.length > 0) {
      this.routeAlternativesReturn.forEach((alt) => {
        const layerId = `route-return-alt-${alt.id}`;
        const sourceId = `route-return-alt-${alt.id}`;
        if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
        if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
      });
    }

    this.routeAlternatives.forEach((alt, index) => {
      const isSelected = this.selectedRouteIndex === index;
      // Couleur paramétrée pour le sélectionné, gris pour les autres
      const color = isSelected ? this.colorOutbound : '#8E8E93';
      const layerId = `route-alt-${alt.id}`;
      const sourceId = `route-alt-${alt.id}`;

      // Nettoyer l'ancien si existant
      if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
      if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);

      // Ajouter la source
      this.map.addSource(sourceId, {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: alt.geometry
        }
      });

      // Ajouter la ligne
      this.map.addLayer({
        id: layerId,
        type: 'line',
        source: sourceId,
        paint: {
          'line-color': color,
          'line-width': isSelected ? 5 : 3,
          'line-opacity': isSelected ? 1.0 : 0.5
        }
      });
    });

    // Ajuster la vue pour voir tous les trajets
    this.fitMapToAllAlternatives();
  }

  // Ajuste la vue de la carte pour voir toutes les alternatives
  fitMapToAllAlternatives(isReturn = false) {
    const alternatives = isReturn ? this.routeAlternativesReturn : this.routeAlternatives;
    if (!alternatives || !alternatives.length) return;

    try {
      const attemptFit = (attempt = 0) => {
        try {
          // Si la map n'est pas prête ou son conteneur est caché, retenter légèrement plus tard
          if (!this.map || typeof this.map.getContainer !== 'function') {
            if (attempt < 5) return setTimeout(() => attemptFit(attempt + 1), 200);
            return;
          }

          const container = this.map.getContainer();
          if (!container || container.offsetWidth === 0 || container.offsetHeight === 0) {
            if (attempt < 5) return setTimeout(() => attemptFit(attempt + 1), 200);
            return;
          }

          const bounds = new maplibregl.LngLatBounds();
          // Ajouter tous les points de toutes les routes
          alternatives.forEach(alt => {
            if (!alt.geometry || !alt.geometry.coordinates) return;
            alt.geometry.coordinates.forEach(coord => bounds.extend(coord));
          });

          // Ajouter les marqueurs de départ/arrivée
          if (this.startCoords) bounds.extend(this.startCoords);
          if (this.endCoords) bounds.extend(this.endCoords);

          // Si bounds est valide, appliquer fitBounds
          if (bounds._ne && bounds._sw) {
            this.map.fitBounds(bounds, { padding: 50, maxZoom: 12 });
          }
        } catch (err) {
          if (attempt < 5) return setTimeout(() => attemptFit(attempt + 1), 200);
          console.warn('fitMapToAllAlternatives failed after retries:', err);
        }
      };

      attemptFit();
    } catch (e) {
      console.warn('fitMapToAllAlternatives error:', e);
    }
  }

  // Attache les event listeners pour les cartes de routes aller
  attachRouteAlternativeListeners() {
    const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
    if (!routeListEl) return;
    
    // Ajouter les handlers de visualisation (clic sur la carte)
    const routeCards = routeListEl.querySelectorAll('.route-alternative-card');
    routeCards.forEach((card) => {
      card.addEventListener('click', (e) => {
        // Ne pas réagir si c'est le bouton qui est cliqué
        if (e.target.classList.contains('btn-select-route')) return;
        const index = parseInt(card.dataset.routeIndex, 10);
        this.highlightRouteAlternative(index);
      });
    });

    const selectBtns = routeListEl.querySelectorAll('.btn-select-route');
    selectBtns.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const index = parseInt(btn.dataset.routeIndex, 10);
        // Si c'est déjà sélectionné et qu'on clique sur "Annuler"
        if (btn.classList.contains('btn-cancel') && this.selectedRouteIndex === index) {
          this.deselectRouteAlternative();
        } else {
          this.selectRouteAlternative(index);
          // Passer directement à l'étape suivante
          setTimeout(() => {
            this.proceedToAdjustments();
          }, 300);
        }
      });
    });
  }

  // Attache les event listeners pour les cartes de routes retour
  attachReturnRouteAlternativeListeners() {
    const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
    if (!routeListEl) return;
    
    // Ajouter les handlers de visualisation (clic sur la carte)
    const routeCards = routeListEl.querySelectorAll('.route-alternative-card');
    routeCards.forEach((card) => {
      card.addEventListener('click', (e) => {
        // Ne pas réagir si c'est le bouton qui est cliqué
        if (e.target.classList.contains('btn-select-route')) return;
        const index = parseInt(card.dataset.routeIndex, 10);
        this.highlightReturnRouteAlternative(index);
      });
    });

    const selectBtns = routeListEl.querySelectorAll('.btn-select-route');
    selectBtns.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const index = parseInt(btn.dataset.routeIndex, 10);
        // Si c'est déjà sélectionné et qu'on clique sur "Annuler"
        if (btn.classList.contains('btn-cancel') && this.selectedRouteIndexReturn === index) {
          this.deselectReturnRouteAlternative();
        } else {
          this.selectReturnRouteAlternative(index);
          setTimeout(() => {
            this.proceedToAdjustmentsFromReturn();
          }, 300);
        }
      });
    });
  }

  // Génère le HTML des cartes d'alternatives
  renderRouteAlternativesHTML() {
    const isDark = this.theme === 'dark';
    const textSecondary = isDark ? '#a0a0a0' : '#8e8e93';
    if (!this.routeAlternatives || !this.routeAlternatives.length) {
      return `<p style="color: ${textSecondary}; text-align: center; padding: 20px;">Aucun itinéraire trouvé</p>`;
    }

    const isRSE = this.isRseMode();

    return this.routeAlternatives.map((alt, index) => {
      const isSelected = this.selectedRouteIndex === index;
      
      // Formater distance et durée
      const distanceKm = (alt.distance / 1000).toFixed(0);
      const durationHours = Math.floor(alt.duration / 3600);
      const durationMins = Math.round((alt.duration % 3600) / 60);
      const durationStr = durationHours > 0 
        ? `${durationHours}h${String(durationMins).padStart(2, '0')}`
        : `${durationMins} min`;

      // Estimer le prix des péages de manière réaliste
      // Formule approximative : ~0.10€/km sur autoroute française
      let tollsStr = '0€';
      let routeLabel = `Trajet ${index + 1}`;
      
      if (alt.hasTolls) {
        const estimatedTolls = Math.round((alt.distance / 1000) * 0.10);
        tollsStr = `~${estimatedTolls}€`;
      } else if (alt.noTollRoute) {
        // Garder "Trajet X" au lieu de "Sans péage"
        tollsStr = '0€ ✓';
      }

      // Via (villes traversées) - afficher jusqu'à 4 villes
      const viaStr = alt.waypoints && alt.waypoints.length 
        ? alt.waypoints.slice(0, 4).join(' • ')
        : 'Itinéraire direct';

      // En mode RSE : afficher uniquement la distance (pas de durée, pas de péages)
      if (isRSE) {
        return `
          <div class="route-alternative-card ${isSelected ? 'selected' : ''}" data-route-index="${index}">
            <div class="route-header">
              <div class="route-title">
                <span class="route-badge">Trajet domicile - travail</span>
              </div>
              <div class="checkmark">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M20 6L9 17l-5-5" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
            </div>
            <div class="route-meta">
              <div class="route-meta-item">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 12h18M3 6h18M3 18h18" stroke="currentColor" stroke-width="2"/>
                </svg>
                <strong>Distance:</strong>
                <span>${distanceKm} km</span>
              </div>
            </div>
            <div class="route-via">
              <strong>Itinéraire</strong>
              ${viaStr}
            </div>
            <button class="btn-select-route ${isSelected ? 'btn-cancel' : ''}" data-route-index="${index}">
              ${isSelected ? 'Annuler la sélection' : 'Valider'}
            </button>
          </div>
        `;
      }

      // Mode normal (ponctuel/récurrent) : afficher durée, distance, péages
      return `
        <div class="route-alternative-card ${isSelected ? 'selected' : ''}" data-route-index="${index}">
          <div class="route-header">
            <div class="route-title">
              <span class="route-badge">${routeLabel}</span>
            </div>
            <div class="checkmark">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M20 6L9 17l-5-5" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
          <div class="route-meta">
            <div class="route-meta-item">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
                <path d="M12 6v6l4 2" stroke="currentColor" stroke-width="2"/>
              </svg>
              <strong>Durée:</strong>
              <span>${durationStr}</span>
            </div>
            <div class="route-meta-item">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 12h18M3 6h18M3 18h18" stroke="currentColor" stroke-width="2"/>
              </svg>
              <strong>Distance:</strong>
              <span>${distanceKm} km</span>
            </div>
            <div class="route-meta-item">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/>
                <path d="M3 9h18M9 3v18" stroke="currentColor" stroke-width="2"/>
              </svg>
              <strong>Péages:</strong>
              <span>${tollsStr}</span>
            </div>
          </div>
          <div class="route-via">
            <strong>Itinéraire</strong>
            ${viaStr}
          </div>
          <button class="btn-select-route ${isSelected ? 'btn-cancel' : ''}" data-route-index="${index}">
            ${isSelected ? 'Annuler la sélection' : 'Choisir'}
          </button>
        </div>
      `;
    }).join('');
  }

  // Highlight (visualisation) d'un trajet alternatif ALLER - gris foncé et plus large
  highlightRouteAlternative(index) {
    if (!this.routeAlternatives || index < 0 || index >= this.routeAlternatives.length) {
      console.warn('highlightRouteAlternative: invalid index', index);
      return;
    }

    console.log('Highlighting route ALLER:', index);

    // Mettre à jour les lignes sur la carte - TOUS EN GRIS
    this.routeAlternatives.forEach((alt, i) => {
      const layerId = `route-alt-${alt.id}`;
      if (this.map.getLayer(layerId)) {
        const isHighlighted = i === index;
        // Celui survolé : gris foncé (#6B7280) et large (6px)
        // Les autres : gris clair (#8E8E93) et fin (3px)
        const color = '#8E8E93'; // Toujours gris
        const width = isHighlighted ? 6 : 3;
        const opacity = isHighlighted ? 1.0 : 0.4;
        
        this.map.setPaintProperty(layerId, 'line-color', color);
        this.map.setPaintProperty(layerId, 'line-width', width);
        this.map.setPaintProperty(layerId, 'line-opacity', opacity);
      }
    });
  }

  // Sélectionne un trajet alternatif ALLER (bouton "Choisir")
  selectRouteAlternative(index) {
    // Vérifier le mode actuel pour savoir si on sélectionne aller ou retour
    if (this.currentRouteSelectionMode === 'return') {
      // On est sur la page de sélection du retour, rediriger vers la bonne fonction
      this.selectReturnRouteAlternative(index);
      return;
    }
    
    // Mode 'outbound' : sélection de l'aller
    if (!this.routeAlternatives || index < 0 || index >= this.routeAlternatives.length) {
      console.warn('selectRouteAlternative: invalid index', index);
      return;
    }

    // Si on change de route aller, réinitialiser le retour
    if (this.selectedRouteIndex !== null && this.selectedRouteIndex !== index) {
      console.log('🔄 Changement de route aller détecté - réinitialisation du retour');
      this.selectedRouteIndexReturn = null;
      this.returnRoute = null;
      this.retLegs = [];
      this.lastReturnRouteDistanceMeters = null;
      // Nettoyer les routes retour de la carte
      if (this.routeAlternativesReturn && this.routeAlternativesReturn.length > 0) {
        this.routeAlternativesReturn.forEach((alt) => {
          const layerId = `route-return-alt-${alt.id}`;
          const sourceId = `route-return-alt-${alt.id}`;
          if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
          if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
        });
      }
      this.routeAlternativesReturn = []; // Réinitialiser les alternatives retour
    }

    this.selectedRouteIndex = index;
    const selected = this.routeAlternatives[index];

    // Mettre à jour le visuel des cartes
    const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
    if (routeListEl) {
      const cards = routeListEl.querySelectorAll('.route-alternative-card');
      cards.forEach((card, i) => {
        if (i === index) {
          card.classList.add('selected');
          const badge = card.querySelector('.route-badge');
          if (badge) badge.style.background = this.colorOutbound;
        } else {
          card.classList.remove('selected');
          const badge = card.querySelector('.route-badge');
          if (badge) badge.style.background = '#8e8e93';
        }
      });
    }

    // Mettre à jour les couleurs et opacités des lignes sur la carte
    this.routeAlternatives.forEach((alt, i) => {
      const layerId = `route-alt-${alt.id}`;
      if (this.map.getLayer(layerId)) {
        const isSelected = i === index;
        const color = isSelected ? this.colorOutbound : '#8E8E93';
        this.map.setPaintProperty(layerId, 'line-color', color);
        this.map.setPaintProperty(layerId, 'line-opacity', isSelected ? 1.0 : 0.5);
        this.map.setPaintProperty(layerId, 'line-width', isSelected ? 5 : 3);
      }
    });

    // Stocker les données de la route sélectionnée
    this.outRoute = {
      distance: selected.distance,
      duration: selected.duration,
      geometry: selected.geometry
    };
    this.outLegs = selected.legs || [];
    this.lastRouteDistanceMeters = selected.distance;

    // Si la carte summary existe, mettre à jour les routes et buffers
    if (this.summaryMap) {
      this.displaySummaryRoutes();
      const checkbox = this.shadowRoot.getElementById('accept-intermediate-passengers');
      const timeSlider = this.shadowRoot.getElementById('detour-time-slider');
      if (checkbox?.checked && timeSlider) {
        const minutes = parseInt(timeSlider.value, 10);
        const avgSpeedKmH = 50;
        const bufferWidthKm = avgSpeedKmH * (minutes / 60) * 0.5;
        this.updateSummaryDetourBuffers(bufferWidthKm);
      }
    }

    console.log('Route alternative ALLER sélectionnée:', index, selected);
  }

  // Désélectionne le trajet aller
  deselectRouteAlternative() {
    console.log('🔄 Désélection du trajet aller');
    this.selectedRouteIndex = null;
    this.outRoute = null;
    this.outLegs = [];
    this.lastRouteDistanceMeters = null;

    // Mettre à jour le visuel des cartes
    const routeListEl = this.shadowRoot.getElementById('route-alternatives-list');
    if (routeListEl) {
      const cards = routeListEl.querySelectorAll('.route-alternative-card');
      cards.forEach((card) => {
        card.classList.remove('selected');
        const badge = card.querySelector('.route-badge');
        if (badge) badge.style.background = '#8e8e93';
        const btn = card.querySelector('.btn-select-route');
        if (btn) {
          btn.classList.remove('btn-cancel');
          btn.textContent = 'Choisir';
        }
      });
    }

    // Remettre toutes les lignes en gris
    this.routeAlternatives.forEach((alt) => {
      const layerId = `route-alt-${alt.id}`;
      if (this.map.getLayer(layerId)) {
        this.map.setPaintProperty(layerId, 'line-color', '#8E8E93');
        this.map.setPaintProperty(layerId, 'line-opacity', 0.5);
        this.map.setPaintProperty(layerId, 'line-width', 3);
      }
    });
  }

  // Passe à l'étape 3 (ajustements) avec le trajet sélectionné
  async proceedToAdjustments() {
    if (this.selectedRouteIndex === null) {
      alert('Veuillez sélectionner un itinéraire');
      return;
    }

    const selected = this.routeAlternatives[this.selectedRouteIndex];
    if (!selected) {
      alert('Erreur : trajet non trouvé');
      return;
    }

    // Nettoyer les anciennes alternatives de la carte
    this.routeAlternatives.forEach((alt) => {
      const layerId = `route-alt-${alt.id}`;
      const sourceId = `route-alt-${alt.id}`;
      if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
      if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
    });

    // Dessiner uniquement le trajet sélectionné en style principal
    if (this.map.getSource("route")) {
      if (this.map.getLayer(this.routeLayerId)) {
        this.map.removeLayer(this.routeLayerId);
      }
      this.map.removeSource("route");
    }

    this.map.addSource("route", {
      type: "geojson",
      data: {
        type: "Feature",
        geometry: selected.geometry
      }
    });

    this.map.addLayer({
      id: this.routeLayerId,
      type: "line",
      source: "route",
      paint: {
        "line-color": this.colorOutbound,
        "line-width": 5
      }
    });

    // En mode RSE : passer à l'étape 3 (récapitulatif CO2)
    if (this.isRseMode()) {
      console.log('Mode RSE : passage à l\'étape 3 (récapitulatif CO2)');
      this.setOfferStep(3);
      return;
    }

    // Si trajet retour activé, passer à l'étape 3 (choix itinéraire retour)
    // Sinon, passer directement aux ajustements
    if (this.hasReturnTrip) {
      // Calculer les alternatives pour le retour (sens inverse)
      await this.fetchReturnRouteAlternatives();
      this.setOfferStep(3); // Étape 3 = choix itinéraire retour
    } else {
      // Pas de retour, passer directement aux ajustements
      try { this.updateOutboundTimeline(); } catch(_) {}
      try { this.updateSegmentPrices(); } catch(_) {}
      this.setOfferStep(3); // Étape 3 = ajustements (quand pas de retour)
    }
  }

  async drawRouteOSRM() {
    if (!this.startCoords || !this.endCoords) return;
    this.setMapLoading(true);
    try {

    // Supprime la source/layer s'ils existent déjà
    if (this.map.getSource("route")) {
      if (this.map.getLayer(this.routeLayerId)) {
        this.map.removeLayer(this.routeLayerId);
      }
      this.map.removeSource("route");
    }

    // Construit la chaîne de coordonnées avec étapes intermédiaires
    const coordsList = [
      this.startCoords,
      ...this.stopCoords.filter(Boolean),
      this.endCoords
    ];
    const coordStr = coordsList.map(c => `${c[0]},${c[1]}`).join(';');

    // Pas de ligne pointillée sur la carte (baseline) – demandé côté encarts uniquement

    const url = `https://router.project-osrm.org/route/v1/driving/${coordStr}?overview=full&geometries=geojson`;
    const res = await fetch(url);
    const data = await res.json();
    if (!data.routes || !data.routes.length) return;
    const routeGeojson = {
      type: "Feature",
      geometry: data.routes[0].geometry
    };
    // Mémorise la distance pour le prix suggéré et les données de route
    try {
      this.lastRouteDistanceMeters = data.routes[0].distance;
      // Stocker les données de la route pour le récapitulatif
      this.outRoute = {
        distance: data.routes[0].distance,
        duration: data.routes[0].duration
      };
      this.outLegs = Array.isArray(data.routes[0].legs) ? data.routes[0].legs : [];
      this.outStops = this.stopCoords.filter(Boolean);
      this.updateSegmentPrices();
    } catch(_) {}

    this.map.addSource("route", {
      type: "geojson",
      data: routeGeojson
    });

    this.map.addLayer({
      id: this.routeLayerId,
      type: "line",
      source: "route",
      paint: {
        "line-color": this.colorOutbound,
        "line-width": 4
      }
    });
    } finally {
      this.setMapLoading(false);
    }
  }

  

  computeBasePrice(distanceKm, includeTolls = false) {
    // Tarification BlaBlaCar officielle (2024-2025):
    // - 0,08 €/km pour les 400 premiers km
    // - 0,06 €/km au-delà de 400 km (tarif dégressif longue distance)
    // - Minimum 2€
    // - Arrondi au 0,50€ le plus proche
    
    let price = 0;
    
    if (distanceKm <= 400) {
      // Tarif standard
      price = distanceKm * 0.08;
    } else {
      // Tarif dégressif au-delà de 400 km
      price = (400 * 0.08) + ((distanceKm - 400) * 0.06);
    }
    
    // Majoration de 15% si péages inclus
    if (includeTolls) {
      price *= 1.15;
    }
    
    // Arrondi au 0,50€ le plus proche (ex: 3,20€ → 3,00€, 3,40€ → 3,50€)
    price = Math.round(price * 2) / 2;
    
    // Prix minimum : 2€
    return Math.max(2, price);
  }

  updateSegmentPrices() {
    try {
      const outEl = this.shadowRoot.getElementById('segment-prices-out');
      const retEl = this.shadowRoot.getElementById('segment-prices-ret');
      const retWrap = this.shadowRoot.getElementById('ret-prices-wrap');
      if (outEl) outEl.innerHTML = '';
      if (retEl) retEl.innerHTML = '';
      if (!this.startCoords || !this.endCoords) return;
      // Construction de la séquence des points de montée potentiels
      const points = [this.startCoords, ...this.stopCoords.filter(Boolean), this.endCoords];
      if (points.length < 2) return;
      // Calcul cumulatif des distances point->destination
      const includeTolls = this.includeTolls && this.includeTolls.checked;
      const totalDistanceMeters = this.lastRouteDistanceMeters || 0;
      // Approximation: on répartit la distance totale proportionnellement aux segments Haversine successifs
      // 1. Distances par segments
      const segs = [];
      for (let i = 0; i < points.length - 1; i++) {
        const d = this.haversineMeters(points[i], points[i+1]);
        segs.push(d);
      }
      const sumSegs = segs.reduce((a,b)=>a+b,0) || 1;
      // 2. Distance cumulée depuis chaque point de montée jusqu'à destination (approx proportionnelle)
      // Points de montée: start + chaque stop. La destination finale n'est pas un point de montée.
      const boardingPoints = points.slice(0, points.length - 1); // exclut la destination
      // 3. Pour chaque point de montée i, distance = somme des segments i..end ajustée à totalDistanceMeters
  const prices = [];
      for (let i = 0; i < boardingPoints.length; i++) {
        // Distance restante mesurée sur les segments i..fin
        const rawMeters = segs.slice(i).reduce((a,b)=>a+b,0);
        const proportion = rawMeters / sumSegs;
        const adjustedMeters = proportion * totalDistanceMeters; // rééchelonnage sur la distance OSRM réelle
        const km = adjustedMeters / 1000;
        const p = this.computeBasePrice(km, includeTolls);
        prices.push({ index: i, km, price: p });
      }
      // 4. Rendu OUTBOUND
      const stopLabels = this.shadowRoot.querySelectorAll('input[data-stop-index]');
      this.segmentPricesOut = this.segmentPricesOut || [];
      this.segmentPricesOutManual = this.segmentPricesOutManual || [];
      if (outEl) outEl.innerHTML = prices.map((obj, idx) => {
        let rawLabel;
        if (idx === 0) {
          const fromInput = this.shadowRoot.getElementById('from');
          rawLabel = (fromInput && fromInput.value.trim()) || 'adresse de départ';
        } else {
          // Cherche l'input avec data-stop-index = idx-1
          const inp = Array.from(stopLabels).find(el => parseInt(el.dataset.stopIndex,10) === (idx - 1));
          rawLabel = inp ? (inp.value.trim() || `Étape ${idx}`) : `Étape ${idx}`;
        }
        const toInput = this.shadowRoot.getElementById('to');
        const toLabel = (toInput && toInput.value.trim()) || 'adresse d\'arrivée';
        // Tronquer si trop long (> 38 chars) pour éviter débordement
        const maxLen = 38;
        let startDisp = rawLabel.length > maxLen ? rawLabel.slice(0, maxLen - 1) + '…' : rawLabel;
        let endDisp = toLabel.length > maxLen ? toLabel.slice(0, maxLen - 1) + '…' : toLabel;
        const distStr = obj.km >= 1 ? `${obj.km.toFixed(1)} km` : `${Math.round(obj.km*1000)} m`;
        const manual = !!this.segmentPricesOutManual[idx];
        const value = manual && Number.isFinite(this.segmentPricesOut[idx]) ? this.segmentPricesOut[idx] : obj.price;
        const suggested = obj.price.toFixed(0);
        return `<li data-seg-type="out" data-idx="${idx}">
          <span>${startDisp} → ${endDisp}</span>
          <span class="right">
            <div style="display: flex; align-items: center; gap: 8px;">
              <input class="segment-price" type="number" step="1" min="0" inputmode="decimal" data-seg-type="out" data-idx="${idx}" value="${Math.round(value)}" />
              <span style="font-size: 18px; font-weight: 700; color: #34c759;font-family:${this.fontFamily};">€</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; font-size: 11px;font-family:${this.fontFamily};">
              ${!manual ? `<span class="suggested-price">Prix conseillé</span>` : `<span class="suggested-price" style="color: #8e8e93;">Modifié • Conseillé: ${suggested}€</span>`}
              <span class="dist" style="color: #8e8e93;">${distStr}</span>
            </div>
          </span>
        </li>`;
      }).join('');

      // 5. Rendu RETURN si activé
      const returnCheckbox = this.shadowRoot.getElementById('return');
      if (returnCheckbox && returnCheckbox.checked && retEl) {
        const viaStops = (this.shadowRoot.getElementById('return-via-stops') || {}).checked;
        const stopCoords = this.stopCoords.filter(Boolean);
        const retPoints = [this.endCoords, ...(viaStops ? stopCoords.slice().reverse() : []), this.startCoords];
        if (retPoints.length >= 2) {
          const retSegs = [];
          for (let i = 0; i < retPoints.length - 1; i++) retSegs.push(this.haversineMeters(retPoints[i], retPoints[i+1]));
          const retSumSegs = retSegs.reduce((a,b)=>a+b,0) || 1;
          const totalRetMeters = Number.isFinite(this.lastReturnRouteDistanceMeters) && this.lastReturnRouteDistanceMeters > 0 ? this.lastReturnRouteDistanceMeters : retSumSegs;
          // Distances cumulées depuis le départ du retour (Bollaert)
          const cum = [0];
          for (let i = 0; i < retSegs.length; i++) cum[i+1] = cum[i] + retSegs[i];
          // labels retour
          const fromInput = this.shadowRoot.getElementById('from');
          const toInput = this.shadowRoot.getElementById('to');
          const fromLabel = (fromInput && fromInput.value.trim()) || 'adresse de départ';
          const toLabel = (toInput && toInput.value.trim()) || 'adresse d\'arrivée';
          const stopInputs = Array.from(stopLabels);
          const stopNames = stopInputs.map((inp, idx) => (inp.value && inp.value.trim()) || `Étape ${idx+1}`);
          const retStopNames = viaStops ? stopNames.slice().reverse() : [];
          const maxLen = 38;
          // Prépare stockage des valeurs manuelles Retour
          this.segmentPricesRet = this.segmentPricesRet || [];
          this.segmentPricesRetManual = this.segmentPricesRetManual || [];
          // Crée les lignes pour chaque destination du retour (à partir de Bollaert):
          // t = 1..retPoints.length-1 (1-based): j est l'index d'affichage 0..N-1
          retEl.innerHTML = Array.from({length: retPoints.length - 1}, (_, j) => {
            const t = j + 1;
            // Distance de Bollaert jusqu'au point t
            const proportion = cum[t] / retSumSegs;
            const km = (proportion * totalRetMeters) / 1000;
            const suggested = this.computeBasePrice(km, this.includeTolls && this.includeTolls.checked);
            // Libellés: toujours Bollaert (toLabel) → destination
            const destLabel = (t < retPoints.length - 1)
              ? (retStopNames[t - 1] || `Étape ${t}`)
              : fromLabel;
            const startLabel = toLabel; // toujours depuis le stade au retour
            let sDisp = startLabel.length > maxLen ? startLabel.slice(0, maxLen - 1) + '…' : startLabel;
            let eDisp = destLabel.length > maxLen ? destLabel.slice(0, maxLen - 1) + '…' : destLabel;
            const distStr = km >= 1 ? `${km.toFixed(1)} km` : `${Math.round(km*1000)} m`;
            const manual = !!this.segmentPricesRetManual[j];
            const value = manual && Number.isFinite(this.segmentPricesRet[j]) ? this.segmentPricesRet[j] : suggested;
            const suggestedStr = suggested.toFixed(0);
            return `<li data-seg-type="ret" data-idx="${j}">
              <span>${sDisp} → ${eDisp}</span>
              <span class="right">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <input class="segment-price" type="number" step="1" min="0" inputmode="decimal" data-seg-type="ret" data-idx="${j}" value="${Math.round(value)}" />
                  <span style="font-size: 18px; font-weight: 700; color: #34c759;font-family:${this.fontFamily};">€</span>
                </div>
                <div style="display: flex; gap: 8px; align-items: center; font-size: 11px;font-family:${this.fontFamily};">
                  ${!manual ? `<span class="suggested-price">Prix conseillé</span>` : `<span class="suggested-price" style="color: #8e8e93;">Modifié • Conseillé: ${suggestedStr}€</span>`}
                  <span class="dist" style="color: #8e8e93;">${distStr}</span>
                </div>
              </span>
            </li>`;
          }).join('');
          if (retWrap) retWrap.style.display = 'block';
        } else {
          if (retWrap) retWrap.style.display = 'none';
        }
      } else {
        if (retWrap) retWrap.style.display = 'none';
      }
    } catch(_) { /* noop */ }
  }

  // ---- Avatar helpers (consistent with header & comment widgets) ----
  // Format a MySQL-like datetime string (YYYY-MM-DD HH:MM[:SS]) to French date with bold time.
  // Returns HTML string e.g. "sam. 22 novembre 2025 à <strong>14:30</strong>".
  formatDateTimeFRHTML(dtStr) {
    try {
      if (!dtStr || typeof dtStr !== 'string') return '—';
      const m = dtStr.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/);
      if (!m) return dtStr;
      const y = parseInt(m[1], 10), mo = parseInt(m[2], 10), d = parseInt(m[3], 10);
      const hh = m[4], mm = m[5];
      // Construct local date to avoid timezone shift
      const date = new Date(y, mo - 1, d, parseInt(hh,10), parseInt(mm,10));
      const datePart = new Intl.DateTimeFormat('fr-FR', {
        weekday: 'short', day: '2-digit', month: 'long', year: 'numeric'
      }).format(date);
      const timePart = `${hh}:${mm}`;
      return `${datePart} à <strong>${timePart}</strong>`;
    } catch(_) { return dtStr || '—'; }
  }

  isFutureDateTime(dtStr) {
    try {
      if (!dtStr || typeof dtStr !== 'string') return false;
      const m = dtStr.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/);
      if (!m) return false;
      const y = parseInt(m[1],10), mo = parseInt(m[2],10), d = parseInt(m[3],10);
      const hh = parseInt(m[4],10), mm = parseInt(m[5],10);
      const when = new Date(y, mo-1, d, hh, mm);
      return when.getTime() > Date.now();
    } catch(_) { return false; }
  }

  getAvatarUrlForUser(uid) {
    const DEFAULT = '/static/images/players/nophoto.png';
    if (!uid) return DEFAULT;
    const idStr = String(uid);
    // If it's the currently logged-in user, try to reuse header image to avoid extra fetch
    try {
      if (window.userId && String(window.userId) === idStr) {
        const headerImg = document.querySelector('#user-wrapper img, #user-avatar-img');
        if (headerImg && headerImg.src) return headerImg.src;
      }
    } catch(_) {}
    // Future: window.cachedUserAvatars could be hydrated elsewhere (Firestore). Use if present.
    try { if (window.cachedUserAvatars && window.cachedUserAvatars[idStr]) return window.cachedUserAvatars[idStr]; } catch(_) {}
    // Default storage pattern from /api/upload_avatar: /static/avatars/<uid>/avatar.jpg
    return `/static/avatars/${idStr}/avatar.jpg`;
  }

  getAvatarHtml(uid) {
    const idStr = uid ? String(uid) : null;
    const url = this.getAvatarUrlForUser(idStr);
    // Keep a fixed-size fallback image instead of replacing with a letter for consistent layout
    return `<div class="avatar-circle"><img src="${url}" alt="Photo conducteur" onerror="this.onerror=null;this.src='/static/images/players/nophoto.png';" /></div>`;
  }

  async fetchCarpoolOffers(force = false) {
    // Réutilise cache 60s pour éviter surcharges
    const now = Date.now();
    if (!force && this._offers && this._offersFetchedAt && (now - this._offersFetchedAt) < 60000) {
      if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
      return;
    }
    const container = this.shadowRoot.getElementById('find-offers-inner');
    if (container) container.setAttribute('aria-busy','true');
    try {
      const res = await fetch('/api/carpool', { credentials: 'include' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      this._offers = Array.isArray(data.offers) ? data.offers : (Array.isArray(data) ? data : []);
      this._offersFetchedAt = now;
      console.log(`✅ ${this._offers.length} offres reçues du backend (déjà filtrées par zones_intersect avec Shapely)`);
      if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
    } catch(e) {
      console.error('fetchCarpoolOffers error', e);
      if (this.shadowRoot.getElementById('find-offers-inner')) {
        this.shadowRoot.getElementById('find-offers-inner').innerHTML = '<div style="padding:16px;color:#c00;">Erreur chargement</div>';
      }
    } finally {
      if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
      if (container) container.removeAttribute('aria-busy');
    }
  }


  async resolveSites() {
    try {
      console.log('🔄 Résolution des sites avec le backend...');
      
      const response = await fetch('/api/v2/sites/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: parseInt(this.companyId),
          sites: this.companySites  // [{name, address}, ...] sans ID
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        this.companySites = data.sites;  // Maintenant avec IDs
        console.log('✅ Sites résolus:', this.companySites);
      } else {
        console.error('❌ Erreur résolution sites:', await response.text());
      }
    } catch (e) {
      console.error('❌ Erreur résolution sites:', e);
    }
  }

  async loadTripCount() {
    try {
      // Mode récurrent ou RSE : compter les offres récurrentes actives de l'entreprise
      if ((this.isRecurrentMode() || this.isRseMode()) && this.companyId) {
        const response = await fetch(`/api/v2/offers/recurrent/count?company_id=${this.companyId}`);
        if (response.ok) {
          const data = await response.json();
          const count = data.count || 0;
          const header = this.shadowRoot.getElementById('find-header-count');
          if (header) {
            header.textContent = `${count} collègue${count > 1 ? 's' : ''}`;
          }
        }
        return;
      }
      
      // Mode ponctuel : compter les offres ponctuelles
      const response = await fetch(`${this.API_URL}/api/carpool/count`);
      if (response.ok) {
        const data = await response.json();
        const count = data.total_trips || 0;
        const header = this.shadowRoot.getElementById('find-header-count');
        if (header) {
          header.textContent = `${count} trajet${count > 1 ? 's' : ''}`;
        }
      }
    } catch(e) {
      console.warn('Failed to load trip count:', e);
    }
  }

  async fetchCarpoolOffersNearPoint(lon, lat, radiusMeters) {
    const container = this.shadowRoot.getElementById('find-offers-inner');
    if (container) container.setAttribute('aria-busy', 'true');
    
    // Afficher un message de calcul en cours
    const searchBtn = this.shadowRoot.getElementById('find-search-btn');
    let statusDiv = this.shadowRoot.getElementById('detour-calc-status');
    if (!statusDiv && searchBtn) {
      statusDiv = document.createElement('div');
      statusDiv.id = 'detour-calc-status';
      statusDiv.style.cssText = 'margin-top:8px;font-size:13px;color:#6b7280;text-align:center;';
      searchBtn.parentNode.insertBefore(statusDiv, searchBtn.nextSibling);
    }
    
    try {
      // Utiliser un radius backend large (50km) pour capter toutes les offres pertinentes
      // Le filtre intelligent frontend (buffer temps) fera le tri précis
      const backendRadius = Math.max(radiusMeters, 50000); // Min 50km pour capter routes passant près du point
      const eventId = this.getAttribute('event-id') || '';
      const eventParam = eventId ? `&event_id=${encodeURIComponent(eventId)}` : '';
      const url = `/api/v2/offers/search?lon=${lon}&lat=${lat}&radius=${backendRadius}${eventParam}`;
      const res = await fetch(url, { credentials: 'include' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      this._offers = Array.isArray(data) ? data : [];
      this._offersFetchedAt = Date.now();
      
      console.log(`✅ ${this._offers.length} offres reçues du backend (déjà filtrées par zones_intersect avec Shapely)`);
      
      // Normalize coordinates from backend (JSON strings or objects → arrays [lon,lat])
      this._offers.forEach(offer => {
        // Parse JSON strings if needed
        if (typeof offer.departure_coords === 'string') {
          try { offer.departure_coords = JSON.parse(offer.departure_coords); } catch(e) {}
        }
        if (typeof offer.destination_coords === 'string') {
          try { offer.destination_coords = JSON.parse(offer.destination_coords); } catch(e) {}
        }
        
        // Convert objects {lat,lon} to arrays [lon,lat]
        if (offer.departure_coords && typeof offer.departure_coords === 'object' && !Array.isArray(offer.departure_coords)) {
          offer.departure_coords = [offer.departure_coords.lon, offer.departure_coords.lat];
        }
        if (offer.destination_coords && typeof offer.destination_coords === 'object' && !Array.isArray(offer.destination_coords)) {
          offer.destination_coords = [offer.destination_coords.lon, offer.destination_coords.lat];
        }
      });
      
      // Hydrate user profiles
      try { await this.hydrateUserProfilesFromFirestore(); } catch(_) {}
      
      // Le backend a déjà filtré les offres avec zones_intersect() qui utilise Shapely (robuste)
      // Pas besoin de refiltrer côté frontend avec pointInPolygon() qui peut avoir des bugs
      // On marque juste les offres qui ne nécessitent pas de détour (départ/arrivée dans le rayon)
      this._offers.forEach(offer => {
        const details = offer.details;
        if (details && details.fromCoords && details.toCoords) {
          const distFromStart = this.haversineMeters([lon, lat], details.fromCoords);
          const distFromEnd = this.haversineMeters([lon, lat], details.toCoords);
          
          // Si départ ou arrivée dans le cercle → pas de détour nécessaire
          if (distFromStart <= radiusMeters || distFromEnd <= radiusMeters) {
            offer._noDetourNeeded = true;
            offer._detourCalculated = false;
          }
        }
      });
      
      // Afficher immédiatement les offres
      this.renderFindOffersFiltered();
      
      // Calculer les détours en arrière-plan avec affichage progressif
      if (statusDiv) statusDiv.textContent = `Calcul des détours optimaux pour ${this._offers.length} trajet(s)...`;
      
      this.calculateDetoursForOffers(lon, lat).then(() => {
        if (statusDiv) {
          statusDiv.textContent = '✓ Calculs terminés';
          setTimeout(() => { if (statusDiv) statusDiv.textContent = ''; }, 2000);
        }
      }).catch(e => {
        console.error('Error calculating detours:', e);
        if (statusDiv) statusDiv.textContent = '⚠ Erreur calcul détours';
      });
      
    } catch (e) {
      console.error('fetchCarpoolOffersNearPoint error', e);
      this._offers = [];
      this._offersError = true;
      if (statusDiv) statusDiv.textContent = '⚠ Erreur lors de la recherche';
    } finally {
      if (container) container.setAttribute('aria-busy', 'false');
    }
  }

  // Calculer les détours, nouveaux prix et horaires pour toutes les offres
  async calculateDetoursForOffers(searchLon, searchLat) {
    console.log('calculateDetoursForOffers called with', this._offers.length, 'offers');
    if (!Array.isArray(this._offers) || this._offers.length === 0) return;
    
    // Utiliser le vrai rayon de recherche au lieu d'un seuil fixe
    const distanceThreshold = this.searchRadiusMeters || 5000;
    
    // Préparer les promesses pour paralléliser les calculs
    const detourPromises = this._offers.map(async (offer) => {
      try {
        // Skip si déjà marqué comme sans détour nécessaire ou incompatible
        if (offer._noDetourNeeded || offer._incompatible) {
          console.log('Offer', offer.id, 'already processed as no-detour or incompatible, skipping calculation');
          return;
        }
        
        // Les coordonnées sont dans offer.details (objet avec fromCoords, toCoords, etc.)
        const details = offer.details;
        if (!details) {
          console.log('Offer', offer.id, 'has no details, skipping');
          return;
        }
        
        const fromCoords = details.fromCoords;
        const toCoords = details.toCoords;
        
        if (!fromCoords || !toCoords || !Array.isArray(fromCoords) || !Array.isArray(toCoords)) {
          console.log('Offer', offer.id, 'missing fromCoords or toCoords in details, skipping');
          return;
        }
        
        const distFromStart = this.haversineMeters([searchLon, searchLat], fromCoords);
        const distFromEnd = this.haversineMeters([searchLon, searchLat], toCoords);
        
        console.log('Offer', offer.id, 'distances - fromStart:', distFromStart, 'fromEnd:', distFromEnd, 'threshold:', distanceThreshold);
        
        // PRIORITÉ : vérifier selon le type de trajet (aller/retour)
        const isOutbound = offer.trip_type === 'outbound';
        
        // ALLER : si départ dans le cercle → pas de détour
        // RETOUR : si arrivée dans le cercle → pas de détour
        const relevantDistance = isOutbound ? distFromStart : distFromEnd;
        
        if (relevantDistance <= distanceThreshold) {
          console.log('Offer', offer.id, isOutbound ? 'departure' : 'arrival', 'is within search radius, no detour needed');
          offer._detourCalculated = false;
          offer._noDetourNeeded = true; // Marquer explicitement qu'aucun détour n'est nécessaire
          return;
        }
        
        // Si les DEUX points sont hors du cercle, alors détour nécessaire
        if (distFromStart > distanceThreshold && distFromEnd > distanceThreshold) {
          console.log('Offer', offer.id, 'both points outside radius, needs detour! Calculating...');
        } else {
          // Un des deux points est dans le cercle mais pas le bon → pas compatible
          console.log('Offer', offer.id, 'incompatible with search location');
          offer._detourCalculated = false;
          offer._incompatible = true;
          return;
        }
        
        // Utiliser le point de rencontre suggéré par le backend si disponible
        // (ce point est dans l'intersection zone_conducteur ∩ rayon_passager)
        let meetingAddress = null;
        let meetingCoords = null;
        
        if (offer.suggested_meeting_point && Array.isArray(offer.suggested_meeting_point) && offer.suggested_meeting_point.length >= 2) {
          // Le backend a trouvé un point dans l'intersection réelle
          meetingCoords = offer.suggested_meeting_point;
          console.log('Using backend suggested meeting point:', meetingCoords);
          
          // Reverse geocode pour obtenir une adresse lisible
          try {
            const reverseUrl = `https://api-adresse.data.gouv.fr/reverse/?lon=${meetingCoords[0]}&lat=${meetingCoords[1]}`;
            const reverseRes = await fetch(reverseUrl);
            
            if (reverseRes.ok) {
              const reverseData = await reverseRes.json();
              if (reverseData.features && reverseData.features.length > 0) {
                const feature = reverseData.features[0];
                const props = feature.properties;
                
                // Construire une adresse lisible : préférer city + context plutôt que label avec tous les codes postaux
                if (props.city) {
                  meetingAddress = props.city;
                  // Ajouter le contexte (département) si disponible
                  if (props.context) {
                    const contextParts = props.context.split(',').map(s => s.trim());
                    // Prendre le dernier élément (généralement le département)
                    if (contextParts.length > 0) {
                      meetingAddress += ` (${contextParts[contextParts.length - 1]})`;
                    }
                  }
                } else if (props.name) {
                  meetingAddress = props.name;
                } else {
                  meetingAddress = props.label;
                }
              }
            }
          } catch(e) {
            console.warn('Erreur reverse geocoding:', e);
          }
        } else {
          // Fallback : utiliser le point de recherche du passager (ancienne méthode)
          console.log('No backend meeting point, falling back to search location');
          try {
            const searchUrl = `https://api-adresse.data.gouv.fr/reverse/?lon=${searchLon}&lat=${searchLat}`;
            const searchRes = await fetch(searchUrl);
            
            if (searchRes.ok) {
              const searchData = await searchRes.json();
              if (searchData.features && searchData.features.length > 0) {
                const feature = searchData.features[0];
                const props = feature.properties;
                
                // Construire une adresse lisible : préférer city + context plutôt que label avec tous les codes postaux
                if (props.city) {
                  meetingAddress = props.city;
                  // Ajouter le contexte (département) si disponible
                  if (props.context) {
                    const contextParts = props.context.split(',').map(s => s.trim());
                    // Prendre le dernier élément (généralement le département)
                    if (contextParts.length > 0) {
                      meetingAddress += ` (${contextParts[contextParts.length - 1]})`;
                    }
                  }
                } else if (props.name) {
                  meetingAddress = props.name;
                } else {
                  meetingAddress = props.label;
                }
                
                meetingCoords = feature.geometry.coordinates;
              }
            }
          } catch(e) {
            console.warn('Erreur recherche adresse:', e);
          }
        }
        
        if (!meetingCoords) {
          meetingCoords = [searchLon, searchLat];
          meetingAddress = `${searchLat.toFixed(5)}, ${searchLon.toFixed(5)}`;
        }
        
        // Calculer le nouveau trajet avec détour via routing API
        const routeResult = await this.fetchRoute([fromCoords, meetingCoords, toCoords], { overview: 'full' });
        
        if (!routeResult.success) {
          console.warn(`❌ Impossible de calculer le trajet avec détour pour offre ${offerId}`);
          return; // Sortir de cette Promise
        }
        
        const detourData = routeResult.data;
        console.log(`✅ Route calculée via ${routeResult.source}`);
        
        if (detourData && detourData.routes && detourData.routes.length > 0) {
          const detourRoute = detourData.routes[0];
            
            // Calculer la distance depuis le point de rendez-vous jusqu'à la destination
            let passengerDistance = 0;
            let passengerDurationMin = 0;
            
            const passengerRouteResult = await this.fetchRoute([meetingCoords, toCoords], { overview: 'false' });
            if (passengerRouteResult.success && passengerRouteResult.data.routes[0]) {
              passengerDistance = passengerRouteResult.data.routes[0].distance / 1000;
              passengerDurationMin = Math.round(passengerRouteResult.data.routes[0].duration / 60);
            } else {
              // Fallback estimation
              passengerDistance = this.haversineMeters(meetingCoords, toCoords) * 1.3 / 1000;
              passengerDurationMin = Math.round((passengerDistance / 80) * 60); // Estimation à 80 km/h
            }
            
            // Calculer le prix selon la formule BlaBlaCar (distance passager uniquement)
            // Le passager paie pour SA distance (meeting point → destination)
            // Le système BlaBlaCar ne facture PAS le détour au passager
            const newPrice = this.computeBasePrice(passengerDistance, !!details.includeTolls);
            
            // Pour info : distance et prix originaux
            const originalDistance = details.distanceMeters?.outbound ? details.distanceMeters.outbound / 1000 : 0;
            const pricesArr = Array.isArray(details.prices?.out) ? details.prices.out : [];
            let originalPrice = 0;
            if (pricesArr.length) {
              originalPrice = Number(pricesArr[0]) || 0;
            }
            if (!originalPrice && originalDistance) {
              originalPrice = this.computeBasePrice(originalDistance, !!details.includeTolls);
            }
            
            const priceDifference = newPrice - originalPrice;
            
            // Calculer le nouveau temps de trajet
            const originalDuration = details.durationSeconds?.outbound ? Math.round(details.durationSeconds.outbound / 60) : 0;
            const newDuration = Math.round(detourRoute.duration / 60); // Convertir en minutes
            const extraTime = newDuration - originalDuration;
            
            // Ajuster l'horaire de départ pour toujours arriver à l'heure
            // Si le trajet prend plus de temps, on part plus tôt
            const datetime = offer.datetime;
            let adjustedDepartureTime = '';
            
            if (datetime) {
              const arrivalDateObj = new Date(datetime);
              const departureMs = arrivalDateObj.getTime() - (newDuration * 60000);
              const departureDateObj = new Date(departureMs);
              adjustedDepartureTime = `${String(departureDateObj.getUTCHours()).padStart(2, '0')}:${String(departureDateObj.getUTCMinutes()).padStart(2, '0')}`;
            }
            
            const originalDepartureMs = datetime ? new Date(datetime).getTime() - (originalDuration * 60000) : 0;
            const originalDepartureTime = originalDepartureMs ? `${String(new Date(originalDepartureMs).getUTCHours()).padStart(2, '0')}:${String(new Date(originalDepartureMs).getUTCMinutes()).padStart(2, '0')}` : '';
            
            // Calculer l'heure de pickup (passage chez le client)
            // LOGIQUE CORRECTE : pickupTime = heure arrivée événement - durée trajet passager
            // Le passager doit partir à cette heure pour arriver à temps à l'événement
            let pickupTime = '';
            let pickupDurationMin = 0;
            
            if (datetime && passengerDurationMin) {
              const arrivalDateObj = new Date(datetime);
              // IMPORTANT : Utiliser UTC pour éviter les décalages de fuseau horaire
              const pickupMs = arrivalDateObj.getTime() - (passengerDurationMin * 60000);
              const pickupDateObj = new Date(pickupMs);
              pickupTime = `${String(pickupDateObj.getUTCHours()).padStart(2, '0')}:${String(pickupDateObj.getUTCMinutes()).padStart(2, '0')}`;
              
              // Pour info : durée entre domicile conducteur et point de pickup
              if (detourData.routes[0].legs && detourData.routes[0].legs.length >= 1) {
                const firstLeg = detourData.routes[0].legs[0];
                pickupDurationMin = Math.round(firstLeg.duration / 60);
              }
            }
            
            // Stocker les infos de détour dans l'offre ET dans offer.details
            const detourInfo = {
              meetingPoint: {
                coords: meetingCoords,
                address: meetingAddress,
                distanceFromSearch: this.haversineMeters([searchLon, searchLat], meetingCoords)
              },
              detourRoute: detourRoute, // Objet complet avec geometry + duration
              adjustedPrice: newPrice.toFixed(2),
              originalPrice: originalPrice.toFixed(2),
              priceDifference: priceDifference.toFixed(2),
              passengerDistance: passengerDistance.toFixed(1),
              passengerDurationMin: passengerDurationMin, // Durée trajet passager (pickup → destination)
              adjustedDepartureTime: adjustedDepartureTime,
              originalDepartureTime: originalDepartureTime,
              pickupTime: pickupTime, // Heure de passage chez le client
              pickupDurationMin: pickupDurationMin, // Durée domicile conducteur -> pickup
              extraTime: extraTime,
              fullRouteDistance: (detourRoute.distance / 1000).toFixed(1)
            };
            
            offer._detourCalculated = true;
            offer._detourInfo = detourInfo;
            // Aussi stocker dans details pour que ce soit accessible partout
            offer.details._detourCalculated = true;
            offer.details._detourInfo = detourInfo;
            
            console.log(`✅ Détour calculé pour offre ${offer.id}:
              - Distance totale conducteur: ${(detourRoute.distance / 1000).toFixed(1)} km (avec détour)
              - Distance passager (facturable): ${passengerDistance.toFixed(1)} km (meeting → destination)
              - Durée passager: ${passengerDurationMin} min
              - Prix passager: ${newPrice.toFixed(2)} € (basé sur sa distance uniquement)
              - 🕐 Heure pickup: ${pickupTime} (arrivée ${datetime ? new Date(datetime).getHours() + ':' + String(new Date(datetime).getMinutes()).padStart(2, '0') : '?'} - ${passengerDurationMin}min)
              - 🚗 Heure départ conducteur: ${adjustedDepartureTime}
              - ⏱️ Durée conducteur→pickup: ${pickupDurationMin} min`);
        } else {
          console.warn('❌ No routes in detour response for offer:', offer.id);
        }
      } catch(e) {
        console.warn('❌ Erreur calcul détour pour offre:', offer.id, e);
        offer._detourCalculated = false;
      }
    });
    
    // Exécuter tous les calculs en parallèle
    await Promise.all(detourPromises);
    
    // Afficher une seule fois à la fin
    this.renderFindOffersFiltered();
    
    console.log('Finished calculating detours. Offers with detours:', this._offers.filter(o => o._detourCalculated).length);
  }

  // Fetch displayName/photoURL for offer user_ids, inspired by article-display comments flow
  async hydrateUserProfilesFromFirestore() {
    if (!Array.isArray(this._offers) || this._offers.length === 0) return;
    const uids = Array.from(new Set(this._offers.map(o => o && o.user_id).filter(Boolean).map(String)));
    if (!uids.length) return;
    window.cachedUserAvatars = window.cachedUserAvatars || {};
  let applied = false;
    // 1) Try client-side Firestore (exactly like article-display)
    try {
      const mod = await import('https://www.gstatic.com/firebasejs/11.10.0/firebase-firestore.js');
      const { getFirestore, doc, getDoc } = mod;
      const db = getFirestore();
      const results = await Promise.all(uids.map(async (uid) => {
        try {
          const snap = await getDoc(doc(db, 'users', uid));
          if (snap.exists()) {
            const d = snap.data() || {};
            return { uid, displayName: d.displayName || d.name || null, photoURL: d.photoURL || null };
          }
        } catch(_){ /* noop */ }
        return { uid, displayName: null, photoURL: null };
      }));
  const byUid = Object.fromEntries(results.map(r => [r.uid, r]));
  this._userProfiles = byUid;
      this._offers = this._offers.map(o => {
        try {
          const uid = o && o.user_id ? String(o.user_id) : null;
          if (!uid) return o;
          const info = byUid[uid] || {};
          if (info.photoURL) window.cachedUserAvatars[uid] = info.photoURL;
          return {
            ...o,
            user_display_name: (o.user_display_name && String(o.user_display_name).trim()) || info.displayName || o.user_id
          };
        } catch(_) { return o; }
      });
      applied = true;
    } catch (e) {
      // Firestore not available client-side; will try server batch
    }
    // 2) Fallback to backend batch resolver if Firestore not applied
    if (!applied) {
      try {
        const qs = encodeURIComponent(uids.join(','));
        const resp = await fetch(`/api/users/batch?ids=${qs}`, { credentials: 'include' });
        if (resp.ok) {
          const data = await resp.json();
          const users = (data && data.users) || {};
          this._userProfiles = users;
          this._offers = this._offers.map(o => {
            try {
              const uid = o && o.user_id ? String(o.user_id) : null;
              if (!uid) return o;
              const info = users[uid] || {};
              if (info.photoURL) window.cachedUserAvatars[uid] = info.photoURL;
              return {
                ...o,
                user_display_name: (o.user_display_name && String(o.user_display_name).trim()) || info.displayName || o.user_id
              };
            } catch(_) { return o; }
          });
        }
      } catch(_) { /* keep fallbacks */ }
    }
  }

  // Ensure user profiles exist for given uids in this._userProfiles using Firestore or server batch
  async ensureProfilesForUids(uidsInput) {
    const uids = Array.from(new Set((uidsInput || []).filter(Boolean).map(String)));
    if (!uids.length) return;
    this._userProfiles = this._userProfiles || {};
    const missing = uids.filter(u => !this._userProfiles[u] || !this._userProfiles[u].displayName);
    if (!missing.length) return;
    // Try client Firestore first
    let applied = false;
    try {
      const mod = await import('https://www.gstatic.com/firebasejs/11.10.0/firebase-firestore.js');
      const { getFirestore, doc, getDoc } = mod;
      const db = getFirestore();
      for (const uid of missing) {
        try {
          const snap = await getDoc(doc(db, 'users', uid));
          if (snap.exists()) {
            const d = snap.data() || {};
            const profile = { displayName: d.displayName || d.name || null, photoURL: d.photoURL || null };
            this._userProfiles[uid] = profile;
            if (profile.photoURL) {
              window.cachedUserAvatars = window.cachedUserAvatars || {};
              window.cachedUserAvatars[uid] = profile.photoURL;
            }
          }
        } catch(_) {}
      }
      applied = true;
    } catch(_) {}
    if (!applied) {
      try {
        const qs = encodeURIComponent(missing.join(','));
        const resp = await fetch(`/api/users/batch?ids=${qs}`, { credentials: 'include' });
        if (resp.ok) {
          const data = await resp.json();
          const users = (data && data.users) || {};
          for (const uid of Object.keys(users)) {
            const info = users[uid] || {};
            this._userProfiles[uid] = { displayName: info.displayName || null, photoURL: info.photoURL || null };
            if (info.photoURL) {
              window.cachedUserAvatars = window.cachedUserAvatars || {};
              window.cachedUserAvatars[uid] = info.photoURL;
            }
          }
        }
      } catch(_) {}
    }
  }

  /**
   * Appelle le backend pour calculer une route (évite problèmes CORS)
   * Le backend essaye plusieurs serveurs OSRM avec fallback automatique
   */
  async fetchRoute(waypoints, options = {}) {
    try {
      const response = await fetch('/api/carpool/calculate-route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ waypoints })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('❌ Backend route calculation failed:', errorData);
        return { success: false, error: errorData.error || 'Erreur serveur' };
      }
      
      const result = await response.json();
      
      if (result.error) {
        console.error('❌ Route calculation error:', result.error);
        return { success: false, error: result.error };
      }
      
      // Le backend retourne déjà {routes: [...]} au format OSRM
      const data = {
        code: 'Ok',
        routes: result.routes || []
      };
      
      if (data.routes.length > 0) {
        const route = data.routes[0];
        console.log(`✅ Route calculée via backend: ${(route.distance/1000).toFixed(1)}km, ${(route.duration/60).toFixed(0)}min`);
      }
      
      return { success: true, data, source: 'backend' };
      
    } catch (e) {
      console.error('❌ fetchRoute error:', e);
      return { success: false, error: e.message };
    }
  }

  getDisplayNameForUid(uid, offerOrFallback) {
    const u = uid ? String(uid) : null;
    if (!u) return 'Conducteur';
    try {
      // prefer hydrated profiles map
      if (this._userProfiles) {
        const info = this._userProfiles[u];
        if (info && info.displayName && String(info.displayName).trim()) return String(info.displayName).trim();
      }
      // then offer-provided name from backend (si c'est un objet avec user_display_name)
      if (offerOrFallback && typeof offerOrFallback === 'object' && offerOrFallback.user_display_name && String(offerOrFallback.user_display_name).trim()) {
        return String(offerOrFallback.user_display_name).trim();
      }
      // fallback string si fourni
      if (offerOrFallback && typeof offerOrFallback === 'string') {
        return offerOrFallback;
      }
    } catch(_) {}
    // fallback to uid
    return u;
  }

  extractTime(datetime) {
    // Extrait HH:MM depuis datetime (format: "YYYY-MM-DD HH:MM" ou ISO)
    try {
      if (!datetime) return null;
      const match = String(datetime).match(/(\d{2}):(\d{2})/);
      return match ? `${match[1]}:${match[2]}` : null;
    } catch(_) {
      return null;
    }
  }

  formatDateFR(datetime) {
    // Format: "Lun 2 déc" depuis datetime
    try {
      if (!datetime) return '';
      const date = new Date(datetime);
      const days = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];
      const months = ['jan', 'fév', 'mar', 'avr', 'mai', 'juin', 'juil', 'août', 'sep', 'oct', 'nov', 'déc'];
      return `${days[date.getDay()]} ${date.getDate()} ${months[date.getMonth()]}`;
    } catch(_) {
      return '';
    }
  }

  addMinutes(timeStr, minutes) {
    // Ajoute des minutes à une heure HH:MM et retourne HH:MM
    try {
      if (!timeStr || !minutes) return null;
      const [h, m] = timeStr.split(':').map(Number);
      const totalMinutes = h * 60 + m + minutes;
      const newH = Math.floor(totalMinutes / 60) % 24;
      const newM = totalMinutes % 60;
      return `${String(newH).padStart(2, '0')}:${String(newM).padStart(2, '0')}`;
    } catch(_) {
      return null;
    }
  }

  renderFindOffers() {
    const wrap = this.shadowRoot.getElementById('find-offers');
    const inner = this.shadowRoot.getElementById('find-offers-inner');
    const findHeader = this.shadowRoot.getElementById('find-header');
    const findHeaderCount = this.shadowRoot.getElementById('find-header-count');
    
    if (!wrap || !inner) return;
    const isFind = this.activeTab === 'find';
    
    // Gérer l'affichage du header
    if (findHeader) {
      findHeader.style.display = isFind ? '' : 'none';
    }
    
    wrap.style.display = isFind ? '' : 'none';
    if (!isFind) return;
    
    const offers = this._offers || [];
    
    // Mettre à jour le compteur dans le header
    if (findHeaderCount) {
      const totalCount = offers.reduce((count, o) => {
        const hasReturn = o.details?.returnTrip?.enabled;
        return count + (hasReturn ? 2 : 1); // Compter aller + retour si disponible
      }, 0);
      findHeaderCount.textContent = `${totalCount} trajet${totalCount > 1 ? 's' : ''} disponible${totalCount > 1 ? 's' : ''}`;
    }
    
    // AFFICHER TOUTES LES OFFRES DISPONIBLES (pas de filtrage géographique)
    // Appeler renderFindOffersFiltered sans searchCenterCoords pour afficher tout
    this.renderFindOffersFiltered();
  }

  drawSearchRadius(center, radiusMeters = 3000) {
    if (!this.map || !Array.isArray(center) || center.length !== 2) return;
    const feature = this.createCirclePolygon(center, radiusMeters, 80);
    const srcId = 'search-radius';
    const layerId = 'search-radius-fill';
    if (this.map.getSource(srcId)) {
      const src = this.map.getSource(srcId);
      if (src && src.setData) src.setData(feature);
    } else {
      this.map.addSource(srcId, { type: 'geojson', data: feature });
      this.map.addLayer({
        id: layerId,
        type: 'fill',
        source: srcId,
        paint: { 'fill-color': '#007bff', 'fill-opacity': 0.10, 'fill-outline-color': '#007bff' }
      });
    }
  }

  filterOffersByRadius(center, radiusMeters = 3000) {
    if (!Array.isArray(center)) return this._offers || [];
    const offers = this._offers || [];
    return offers.filter(o => {
      const details = o.details || {};
      const points = [];
      if (Array.isArray(details.fromCoords)) points.push(details.fromCoords);
      if (Array.isArray(details.stops)) {
        for (const s of details.stops) {
          if (Array.isArray(s.coords)) points.push(s.coords);
        }
      }
      return points.some(p => {
        try { return this.haversineMeters(center, p) <= radiusMeters; } catch(_) { return false; }
      });
    });
  }

  filterOffers() {
    // Re-rendre les offres avec les filtres actifs
    if (this.searchCenterCoords) {
      this.renderFindOffersFiltered();
    } else {
      this.renderFindOffers();
    }
  }

  async calculatePickupTimesForOffers(offers, searchPoint, tripType) {
    /**
     * Calcule les horaires de pickup et prix pour chaque offre
     * @param {Array} offers - Liste des offres
     * @param {Array} searchPoint - [lon, lat] du point de recherche
     * @param {String} tripType - 'outbound' ou 'return'
     * @returns {Array} Offres enrichies avec pickup_time et segment_price
     */
    if (!searchPoint || !offers || !offers.length) return offers;
    
    const enrichedOffers = await Promise.all(offers.map(async (offer) => {
      try {
        const response = await fetch(`${this.API_URL}/api/carpool/calculate-pickup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            offer_id: offer.id,
            search_point: searchPoint,
            trip_type: tripType
          })
        });
        
        if (response.ok) {
          const data = await response.json();
          return {
            ...offer,
            _calculated_pickup_time: data.pickup_time,
            _calculated_segment_price: data.segment_price,
            _calculated_pickup_distance_km: data.pickup_distance_km,
            _calculated_detour_time_min: data.detour_time_minutes
          };
        }
      } catch (err) {
        console.warn(`Failed to calculate pickup for offer ${offer.id}:`, err);
      }
      return offer;
    }));
    
    return enrichedOffers;
  }

  async renderFindOffersFiltered() {
    const wrap = this.shadowRoot.getElementById('find-offers');
    const inner = this.shadowRoot.getElementById('find-offers-inner');
    if (!wrap || !inner) return;
    const isFind = this.activeTab === 'find';
    wrap.style.display = isFind ? '' : 'none';
    if (!isFind) return;
    
    // Si aucune recherche n'a encore été effectuée, afficher un message d'invite
    if (!this._offers) { 
      const inviteMessage = '<div style="padding:20px;border:1px solid #ddd;background:#f9f9f9;border-radius:12px;color:#666;text-align:center;font-size:14px;">🔍 Entrez votre adresse de départ et cliquez sur "Rechercher" pour trouver des covoiturages.</div>';
      inner.innerHTML = inviteMessage;
      return; 
    }
    
    const list = this._offers; // Déjà filtré par le backend
    if (!list.length) {
      inner.innerHTML = '<div style="padding:8px;border:1px solid #ccc;background:#fafafa;border-radius:8px;color:#555">Aucun trajet disponible pour cet événement.</div>';
      return;
    }
    
    // Vider le conteneur
    inner.innerHTML = '';
    
    // Afficher chaque offre avec le même style que le mode récurrent
    list.forEach(offer => {
      const card = document.createElement('div');
      card.style.cssText = 'background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); transition: all 0.2s ease; margin-bottom: 12px;';
      
      // Extraire les informations de l'offre
      const driverName = this.getDisplayNameForUid(offer.user_id, offer);
      const seatsAvailable = offer.seats_available !== undefined ? offer.seats_available : offer.seats;
      const isFull = seatsAvailable === 0;
      
      // Vérifier si retour activé
      const details = offer.details || {};
      const hasReturn = details.returnTrip?.enabled;
      
      // Utiliser l'adresse de recherche du passager si disponible, sinon l'adresse de départ du conducteur
      const displayDeparture = this.searchLocationName || offer.departure;
      
      // Formater la date
      let dateLabel = '';
      if (offer.datetime) {
        const date = new Date(offer.datetime);
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        dateLabel = date.toLocaleDateString('fr-FR', options);
      }
      
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
          <div style="flex: 1;">
            <div style="font-size: 16px; font-weight: 700; color: #333; margin-bottom: 8px;">
              👤 ${driverName}
            </div>
            ${dateLabel ? `
            <div style="margin-bottom: 12px;">
              <span style="display: inline-block; padding: 6px 12px; background: ${this.colorOutbound}; color: white; border-radius: 6px; font-size: 13px; font-weight: 600;">
                📅 ${dateLabel}
              </span>
            </div>
            ` : ''}
          </div>
          <div style="text-align: right;">
            <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Places disponibles</div>
            <div style="font-size: 24px; font-weight: 700; color: ${isFull ? '#dc2626' : this.colorOutbound};">
              ${seatsAvailable}
            </div>
            ${isFull ? `
            <div style="font-size: 10px; color: #dc2626; font-weight: 600; margin-top: 4px;">⚠️ COMPLET</div>
            ` : ''}
          </div>
        </div>
        
        <div style="background: #f8fafc; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 12px; ${hasReturn ? 'margin-bottom: 12px; padding-bottom: 12px; border-bottom: 2px solid #e2e8f0;' : ''}">
            <div style="flex: 1;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <div style="color: ${this.colorOutbound}; font-size: 18px;">📍</div>
                <div style="flex: 1;">
                  <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Départ</div>
                  <div style="font-size: 13px; font-weight: 600; color: #1e293b;">${displayDeparture}</div>
                </div>
              </div>
              <div style="margin-left: 26px; height: 20px; border-left: 3px solid ${this.colorOutbound}; margin-bottom: 8px;"></div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="color: ${this.colorOutbound}; font-size: 18px;">${hasReturn ? '🏢' : '🏁'}</div>
                <div style="flex: 1;">
                  <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Arrivée</div>
                  <div style="font-size: 13px; font-weight: 600; color: #1e293b;">${offer.destination}</div>
                </div>
              </div>
            </div>
            <div style="font-size: 11px; color: ${this.colorOutbound}; font-weight: 700; writing-mode: vertical-rl; text-orientation: mixed;">ALLER</div>
          </div>
          
          ${hasReturn ? `
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="flex: 1;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <div style="color: ${this.colorReturn}; font-size: 18px;">🏢</div>
                <div style="flex: 1;">
                  <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Départ</div>
                  <div style="font-size: 13px; font-weight: 600; color: #1e293b;">${offer.destination}</div>
                </div>
              </div>
              <div style="margin-left: 26px; height: 20px; border-left: 3px solid ${this.colorReturn}; margin-bottom: 8px;"></div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="color: ${this.colorReturn}; font-size: 18px;">📍</div>
                <div style="flex: 1;">
                  <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Arrivée</div>
                  <div style="font-size: 13px; font-weight: 600; color: #1e293b;">${displayDeparture}</div>
                </div>
              </div>
            </div>
            <div style="font-size: 11px; color: ${this.colorReturn}; font-weight: 700; writing-mode: vertical-rl; text-orientation: mixed;">RETOUR</div>
          </div>
          ` : ''}
        </div>
        
        <button 
          data-offer-id="${offer.id}"
          class="btn-reserve-ponctual"
          style="width: 100%; background: ${isFull ? '#9ca3af' : (hasReturn ? `linear-gradient(135deg, ${this.colorOutbound} 0%, ${this.colorReturn} 100%)` : this.colorOutbound)}; color: white; border: none; border-radius: 8px; padding: 12px; font-size: 14px; font-weight: 700; cursor: ${isFull ? 'not-allowed' : 'pointer'}; transition: all 0.2s ease;"
          ${isFull ? 'disabled' : ''}
          onmouseover="${isFull ? '' : `this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.15)'`}"
          onmouseout="${isFull ? '' : `this.style.transform='translateY(0)'; this.style.boxShadow='none'`}">
          ${isFull ? '⛔ Complet' : '🚗 Réserver une place'}
        </button>
      `;
      
      inner.appendChild(card);
      
      // Ajouter l'event listener au bouton
      if (!isFull) {
        const reserveBtn = card.querySelector('.btn-reserve-ponctual');
        if (reserveBtn) {
          reserveBtn.addEventListener('click', () => {
            // Stocker l'offre sélectionnée pour afficher le point de rencontre (même système que récurrent)
            this.selectedOffer = offer;
            this.showMeetingPointCheckbox(offer);
            this.openReservationModal(offer);
          });
        }
      }
    });
  }

  _renderOffersWithPickupTimes(currentOffers, opts) {
    const inner = this.shadowRoot.getElementById('find-offers-inner');
    if (!inner) return;
    
    const {
      isOutboundPage,
      requestedSeats,
      cardBg,
      textPrimary,
      textSecondary,
      borderLight,
      btnSecondaryBg,
      btnSecondaryText,
      btnSecondaryBorder
    } = opts;
    
    // Génération des variantes de couleur pour cette page
    const generateColorVariants = (hexColor) => {
      const hex = hexColor.replace('#', '').substring(0, 6);
      const r = parseInt(hex.substr(0, 2), 16);
      const g = parseInt(hex.substr(2, 2), 16);
      const b = parseInt(hex.substr(4, 2), 16);
      const light = `rgb(${Math.round(r + (255 - r) * 0.9)}, ${Math.round(g + (255 - g) * 0.9)}, ${Math.round(b + (255 - b) * 0.9)})`;
      const lighter = `rgb(${Math.round(r + (255 - r) * 0.8)}, ${Math.round(g + (255 - g) * 0.8)}, ${Math.round(b + (255 - b) * 0.8)})`;
      const dark = `rgb(${Math.round(r * 0.4)}, ${Math.round(g * 0.4)}, ${Math.round(b * 0.4)})`;
      const gradient = `rgb(${Math.round(r * 0.85)}, ${Math.round(g * 0.85)}, ${Math.round(b * 0.85)})`;
      return { light, lighter, dark, gradient, base: hexColor };
    };
    
    const activeVariants = isOutboundPage ? generateColorVariants(this.colorOutbound) : generateColorVariants(this.colorReturn);
    const outboundVariants = generateColorVariants(this.colorOutbound);
    const returnVariants = generateColorVariants(this.colorReturn);
    
    // Interface élégante avec onglets modernes et bouton de validation
    const hasOutbound = !!this.selectedOutboundOffer;
    const hasReturn = !!this.selectedReturnOffer;
    const canValidate = hasOutbound || hasReturn;
    
    const pageHeader = `
      <div style="position:relative;margin-bottom:24px;">
        <!-- Barre d'onglets avec bouton de validation -->
        <div style="display:flex;flex-direction:column;gap:8px;">
          <!-- Onglets -->
          <div style="display:flex;gap:0;background:${cardBg};border-radius:12px;padding:4px;box-shadow:0 2px 12px rgba(0,0,0,0.08);position:relative;">
            <button id="find-tab-outbound" style="flex:1;padding:12px 16px;border:none;border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1);position:relative;z-index:2;${
              isOutboundPage
                ? `background:linear-gradient(135deg, ${activeVariants.gradient} 0%, ${activeVariants.base} 100%);color:#fff;transform:translateY(0);box-shadow:0 4px 16px rgba(124,58,237,0.4);` 
                : `background:transparent;color:${this.colorOutbound};`
            };font-family:${this.fontFamily};">
              <div style="display:flex;align-items:center;justify-content:center;gap:6px;position:relative;padding-right:24px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                <span>Aller</span>
                ${hasOutbound 
                  ? `<span style="position:absolute;top:50%;right:4px;transform:translateY(-50%);width:18px;height:18px;border-radius:50%;background:#10b981;border:2px solid ${cardBg};display:flex;align-items:center;justify-content:center;flex-shrink:0;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></span>` 
                  : `<span style="position:absolute;top:50%;right:4px;transform:translateY(-50%);width:18px;height:18px;border-radius:50%;background:${isOutboundPage ? 'rgba(255,255,255,0.2)' : 'transparent'};border:2px solid ${isOutboundPage ? 'rgba(255,255,255,0.5)' : this.colorOutbound};flex-shrink:0;"></span>`}
              </div>
            </button>
            <button id="find-tab-return" style="flex:1;padding:12px 16px;border:none;border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1);position:relative;z-index:2;${
              !isOutboundPage
                ? `background:linear-gradient(135deg, ${returnVariants.gradient} 0%, ${returnVariants.base} 100%);color:#fff;transform:translateY(0);box-shadow:0 4px 16px rgba(236,72,153,0.4);` 
                : `background:transparent;color:${this.colorReturn};`
            };font-family:${this.fontFamily};">
              <div style="display:flex;align-items:center;justify-content:center;gap:6px;position:relative;padding-right:24px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
                <span>Retour</span>
                ${hasReturn 
                  ? `<span style="position:absolute;top:50%;right:4px;transform:translateY(-50%);width:18px;height:18px;border-radius:50%;background:#10b981;border:2px solid ${cardBg};display:flex;align-items:center;justify-content:center;flex-shrink:0;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></span>` 
                  : `<span style="position:absolute;top:50%;right:4px;transform:translateY(-50%);width:18px;height:18px;border-radius:50%;background:${!isOutboundPage ? 'rgba(255,255,255,0.2)' : 'transparent'};border:2px solid ${!isOutboundPage ? 'rgba(255,255,255,0.5)' : this.colorReturn};flex-shrink:0;"></span>`}
              </div>
            </button>
          </div>
          
          <!-- Bouton Valider -->
          <button id="validate-booking-btn" style="width:100%;height:48px;padding:0 24px;border:none;border-radius:12px;font-size:16px;font-weight:700;cursor:${canValidate ? 'pointer' : 'not-allowed'};transition:all 0.3s;background:${canValidate ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : '#e5e7eb'};color:${canValidate ? '#fff' : '#9ca3af'};box-shadow:${canValidate ? '0 4px 16px rgba(16,185,129,0.4)' : 'none'};opacity:${canValidate ? '1' : '0.6'};font-family:${this.fontFamily};"${canValidate ? '' : ' disabled'}>
            Valider
          </button>
        </div>
      </div>`;
  
  // Si aucune offre disponible
  if (!currentOffers.length) {
    const message = isOutboundPage 
      ? 'Aucun trajet aller disponible.'
      : 'Aucun trajet retour disponible.';
    inner.innerHTML = pageHeader + `<div style="padding:16px;border:1px solid #ddd;background:#fafafa;border-radius:12px;color:#666;text-align:center;">${message}</div>`;
    
    // Installer les handlers d'onglets
    this.shadowRoot.getElementById('find-tab-outbound')?.addEventListener('click', () => {
      this.findSearchPage = 'outbound';
      if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
    });
    this.shadowRoot.getElementById('find-tab-return')?.addEventListener('click', () => {
      this.findSearchPage = 'return';
      if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
    });
    
    return;
  }
  
  const cardsHtml = currentOffers.map(o => {
    const tripType = o.tripType; // 'outbound' ou 'return'
    const isOutbound = tripType === 'outbound';
    const dt = o.datetime || '';
    const dep = (o.departure || '').replace(/"/g,'&quot;');
    const dest = (o.destination || '').replace(/"/g,'&quot;');
    const details = o.details || {};
    const offerId = o.id != null ? o.id : '';
    // Utiliser seats_outbound/seats_return si disponible, sinon seats général
    const seats = isOutbound 
      ? (o.seats_outbound != null ? o.seats_outbound : o.seats)
      : (o.seats_return != null ? o.seats_return : o.seats);
    
    // Utiliser seats_available si fourni par le backend (après déduction des réservations)
    // Sinon calculer avec reserved_count
    let remaining;
    if (o.seats_available != null) {
      // Backend a déjà calculé les places disponibles
      remaining = Number(o.seats_available);
    } else {
      // Fallback: calculer avec reserved_count
      const reserved = isOutbound 
        ? Number(o.reserved_count_outbound || o.reserved_count || 0)
        : Number(o.reserved_count_return || 0);
      remaining = (Number.isFinite(Number(seats)) ? Number(seats) - reserved : null);
    }
    
    const full = remaining != null && remaining <= 0;
    const insufficientSeats = remaining != null && remaining < requestedSeats;
    const currentUserId = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
    const isOwner = currentUserId && o.user_id && String(o.user_id) === currentUserId;
    const uid = o.user_id != null ? String(o.user_id) : null;
    const avatarHtml = this.getAvatarHtml(uid);
    const driverName = this.getDisplayNameForUid(uid, o);
    
    // Détection du détour : utiliser les infos précalculées si disponibles
    let isDetour = false;
    let detourInfo = null;
    
    // Debug: voir ce qui est disponible
    console.log(`Offre ${offerId}: _detourCalculated=${o._detourCalculated}, details._detourCalculated=${details._detourCalculated}`, o._detourInfo);
    
    // Vérifier d'abord si l'offre a été marquée comme sans détour nécessaire
    if (o._noDetourNeeded) {
      // Cette offre a été pré-filtrée : pas besoin de détour
      isDetour = false;
      detourInfo = null;
    } else if (o._detourCalculated && o._detourInfo) {
      // Utiliser les données de l'offre directement (priorité)
      isDetour = true;
      detourInfo = {
        meetingPoint: o._detourInfo.meetingPoint,
        adjustedPrice: o._detourInfo.adjustedPrice,
        originalPrice: o._detourInfo.originalPrice,
        priceDifference: o._detourInfo.priceDifference,
        adjustedDepartureTime: o._detourInfo.adjustedDepartureTime,
        originalDepartureTime: o._detourInfo.originalDepartureTime,
        pickupTime: o._detourInfo.pickupTime,
        passengerDistance: o._detourInfo.passengerDistance,
        passengerDurationMin: o._detourInfo.passengerDurationMin,
        extraTime: o._detourInfo.extraTime
      };
    } else if (details._detourCalculated && details._detourInfo) {
      // Utiliser les données précalculées
      isDetour = true;
      detourInfo = {
        searchLocation: details._detourInfo.meetingPoint.address || this.searchLocationName || 'Votre position',
        distanceKm: (details._detourInfo.meetingPoint.distanceFromSearch / 1000).toFixed(1),
        adjustedPrice: details._detourInfo.adjustedPrice,
        originalPrice: details._detourInfo.originalPrice,
        extraCost: details._detourInfo.extraCost,
        adjustedDepartureTime: details._detourInfo.adjustedDepartureTime,
        originalDepartureTime: details._detourInfo.originalDepartureTime,
        pickupTime: details._detourInfo.pickupTime, // Heure de passage chez le client
        passengerDistance: details._detourInfo.passengerDistance, // Distance client -> destination
        extraTime: details._detourInfo.extraTime
      };
    } else if (this.searchCenterCoords && Array.isArray(this.searchCenterCoords) && !o._noDetourNeeded) {
      // Fallback : détection simple si pas précalculé
      const fromCoords = details.fromCoords;
      const toCoords = details.toCoords;
      const distanceThreshold = this.searchRadiusMeters || 5000; // Utiliser le rayon de recherche exact
      
      let distFromStart = fromCoords ? this.haversineMeters(this.searchCenterCoords, fromCoords) : Infinity;
      let distFromEnd = toCoords ? this.haversineMeters(this.searchCenterCoords, toCoords) : Infinity;
      
      // PRIORITÉ : si le départ (ALLER) ou l'arrivée (RETOUR) est dans le cercle, PAS de détour
      if (isOutbound) {
        // Pour l'ALLER : si le départ est dans le cercle, pas de détour
        if (distFromStart <= distanceThreshold) {
          isDetour = false;
        } else if (distFromEnd > distanceThreshold) {
          // Les deux sont hors du cercle → détour
          isDetour = true;
          detourInfo = {
            searchLocation: this.searchLocationName || 'Votre position',
            distanceKm: Math.round(Math.min(distFromStart, distFromEnd) / 1000 * 10) / 10
          };
        }
      } else {
        // Pour le RETOUR : si l'arrivée est dans le cercle, pas de détour
        if (distFromEnd <= distanceThreshold) {
          isDetour = false;
        } else if (distFromStart > distanceThreshold) {
          // Les deux sont hors du cercle → détour
          isDetour = true;
          detourInfo = {
            searchLocation: this.searchLocationName || 'Votre position',
            distanceKm: Math.round(Math.min(distFromStart, distFromEnd) / 1000 * 10) / 10
          };
        }
      }
    }
    
    // Calculer les données selon le type de trajet
    let departureTime, departureDate, arrivalTime, arrivalDate, durationStr, price, priceText;
    let startLocation, endLocation, cardColor, cardLabel;
    let meetingPointLocation = null; // Pour les détours : adresse du point de rendez-vous

    /* detour color helpers moved to constructor: use this.detourColor / this.detourColorDark / this.detourShadow */
    
    if (isOutbound) {
      // TRAJET ALLER
      cardColor = this.colorOutbound;
      cardLabel = 'ALLER';
      
      // Pour les détours, utiliser l'adresse du point de rencontre (meeting point)
      if (isDetour && detourInfo && detourInfo.meetingPoint && detourInfo.meetingPoint.address) {
        meetingPointLocation = detourInfo.meetingPoint.address;
        startLocation = detourInfo.meetingPoint.address; // Afficher le point de pickup
      } else {
        startLocation = dep;
      }
      endLocation = dest;
      
      const arrivalDateObj = dt ? new Date(dt) : null;
      arrivalTime = this.extractTime(dt); // Heure d'arrivée FIXE (événement)
      arrivalDate = this.formatDateFR(dt);
      
      // Pour les détours : calculer la durée depuis le pickup jusqu'à l'arrivée
      // Pour les trajets normaux : utiliser la durée totale
      let distanceKm, durationMin;
      
      if (isDetour && detourInfo && detourInfo.passengerDistance) {
        // Distance que le passager va parcourir (pickup -> destination)
        distanceKm = parseFloat(detourInfo.passengerDistance);
        // Utiliser la durée réelle calculée par OSRM, pas une estimation
        durationMin = detourInfo.passengerDurationMin || Math.round((distanceKm / 80) * 60);
      } else {
        distanceKm = details.distanceMeters?.outbound / 1000;
        const durationSec = details.durationSeconds?.outbound;
        durationMin = durationSec ? Math.round(durationSec / 60) : (distanceKm ? Math.round((distanceKm / 80) * 60) : null);
      }
      
      durationStr = durationMin ? `${Math.floor(durationMin / 60)}h${String(durationMin % 60).padStart(2, '0')}` : null;
      
      // PRIORITÉ : utiliser l'heure de pickup calculée par l'API si disponible
      if (o._calculated_pickup_time) {
        try {
          const pickupDt = new Date(o._calculated_pickup_time);
          departureTime = `${String(pickupDt.getHours()).padStart(2, '0')}:${String(pickupDt.getMinutes()).padStart(2, '0')}`;
          departureDate = this.formatDateFR(o._calculated_pickup_time);
        } catch(err) {
          console.warn('Failed to parse calculated pickup time:', err);
        }
      }
      // Sinon, utiliser l'heure de pickup précalculée dans calculateDetoursForOffers
      else if (isDetour && detourInfo && detourInfo.pickupTime) {
        // Pour l'ALLER avec détour : utiliser pickupTime déjà calculé
        // pickupTime = heure arrivée événement - durée trajet passager (meeting → destination)
        departureTime = detourInfo.pickupTime;
        console.log(`🕐 Utilisation pickupTime pour affichage: ${detourInfo.pickupTime} (offre ${o.id})`);
        console.log(`📊 isDetour=${isDetour}, detourInfo=`, detourInfo);
        
        // Reconstruire la date complète pour departureDate
        if (arrivalDateObj) {
          const [hours, minutes] = detourInfo.pickupTime.split(':').map(Number);
          const pickupDateObj = new Date(arrivalDateObj);
          pickupDateObj.setHours(hours, minutes, 0, 0);
          departureDate = this.formatDateFR(pickupDateObj.toISOString().slice(0, 19).replace('T', ' '));
        }
      } else {
        // Calculer l'heure de DÉPART = arrivée - durée
        if (arrivalDateObj && durationMin) {
          const departureMs = arrivalDateObj.getTime() - (durationMin * 60000);
          const departureDateObj = new Date(departureMs);
          departureTime = this.extractTime(departureDateObj.toISOString().slice(0, 19).replace('T', ' '));
          departureDate = this.formatDateFR(departureDateObj.toISOString().slice(0, 19).replace('T', ' '));
        }
      }
      
      // Prix aller
      const pricesArr = Array.isArray(details.prices?.out) ? details.prices.out : [];
      if (pricesArr.length) {
        const firstVal = Number(pricesArr[0]);
        if (Number.isFinite(firstVal)) price = firstVal;
      }
      if (!price && details.distanceMeters?.outbound) {
        const km = details.distanceMeters.outbound / 1000;
        price = this.computeBasePrice(km, !!details.includeTolls);
      }
      
      // PRIORITÉ : utiliser le prix calculé par l'API si disponible
      if (o._calculated_segment_price) {
        price = parseFloat(o._calculated_segment_price);
      }
      // Sinon, si on a un détour précalculé, utiliser le prix ajusté
      else if (isDetour && detourInfo && detourInfo.adjustedPrice) {
        price = parseFloat(detourInfo.adjustedPrice);
      }
    } else {
      // TRAJET RETOUR
      cardColor = this.colorReturn;
      cardLabel = 'RETOUR';
      
      // Pour les détours RETOUR : le point de rencontre devient l'endLocation (dépôt)
      if (isDetour && detourInfo && detourInfo.meetingPoint && detourInfo.meetingPoint.address) {
        meetingPointLocation = detourInfo.meetingPoint.address;
        startLocation = dest; // Départ du retour = destination de l'événement
        endLocation = detourInfo.meetingPoint.address; // Dépôt = point de rencontre sélectionné à l'aller
      } else {
        startLocation = dest; // Inversé
        endLocation = dep;    // Inversé
      }
      
      const returnDepartureTime = details.returnTrip?.time || null;
      let returnDateObj = null;
      
      if (dt && returnDepartureTime) {
        const matchDate = new Date(dt);
        const [retHH, retMM] = returnDepartureTime.split(':');
        returnDateObj = new Date(matchDate);
        returnDateObj.setHours(parseInt(retHH, 10), parseInt(retMM, 10), 0, 0);
        departureTime = returnDepartureTime; // Heure de départ FIXE (événement)
        departureDate = this.formatDateFR(returnDateObj.toISOString().slice(0, 19).replace('T', ' '));
      }
      
      // Pour les détours : calculer la durée depuis le départ jusqu'au pickup du client
      // Pour les trajets normaux : utiliser la durée totale
      let distanceKm, durationMin;
      
      if (isDetour && detourInfo && detourInfo.passengerDistance) {
        // Distance que le passager va parcourir (pickup -> destination finale)
        distanceKm = parseFloat(detourInfo.passengerDistance);
        // Calculer la durée estimée pour cette distance
        durationMin = Math.round((distanceKm / 80) * 60); // Estimation à 80 km/h
      } else {
        distanceKm = details.distanceMeters?.return / 1000;
        const durationSec = details.durationSeconds?.return;
        durationMin = durationSec ? Math.round(durationSec / 60) : (distanceKm ? Math.round((distanceKm / 80) * 60) : null);
      }
      
      durationStr = durationMin ? `${Math.floor(durationMin / 60)}h${String(durationMin % 60).padStart(2, '0')}` : null;
      
      // PRIORITÉ : utiliser l'heure de pickup calculée par l'API si disponible (pour l'arrivée en retour)
      if (o._calculated_pickup_time) {
        try {
          const pickupDt = new Date(o._calculated_pickup_time);
          arrivalTime = `${String(pickupDt.getHours()).padStart(2, '0')}:${String(pickupDt.getMinutes()).padStart(2, '0')}`;
          arrivalDate = this.formatDateFR(o._calculated_pickup_time);
        } catch(err) {
          console.warn('Failed to parse calculated pickup time:', err);
        }
      }
      // Sinon, utiliser la logique de détour existante
      else if (isDetour && detourInfo && returnDateObj && durationMin) {
        // Pour le RETOUR avec détour :
        // - departureTime reste FIXE (événement)
        // - arrivalTime = heure de dépôt = departureTime + pickupDuration + durationMin
        // Note: pickupDuration est le temps pour aller du départ au point de pickup
        // Simplifions : arrivalTime = departureTime + durée totale du détour
        // Mais on veut afficher la durée depuis le pickup, donc on recalcule
        const arrivalMs = returnDateObj.getTime() + (durationMin * 60000);
        const arrivalDateObj = new Date(arrivalMs);
        arrivalTime = `${String(arrivalDateObj.getHours()).padStart(2, '0')}:${String(arrivalDateObj.getMinutes()).padStart(2, '0')}`;
        arrivalDate = this.formatDateFR(arrivalDateObj.toISOString().slice(0, 19).replace('T', ' '));
      } else if (returnDateObj && durationMin) {
        // Calculer l'heure d'arrivée normale
        const arrivalMs = returnDateObj.getTime() + (durationMin * 60000);
        const arrivalDateObj = new Date(arrivalMs);
        arrivalTime = this.extractTime(arrivalDateObj.toISOString().slice(0, 19).replace('T', ' '));
        arrivalDate = this.formatDateFR(arrivalDateObj.toISOString().slice(0, 19).replace('T', ' '));
      }
      
      // Prix retour
      const pricesArr = Array.isArray(details.prices?.ret) ? details.prices.ret : [];
      if (pricesArr.length) {
        const firstVal = Number(pricesArr[0]);
        if (Number.isFinite(firstVal)) price = firstVal;
      }
      if (!price && details.distanceMeters?.return) {
        const km = details.distanceMeters.return / 1000;
        price = this.computeBasePrice(km, !!details.includeTolls);
      }
      
      // PRIORITÉ : utiliser le prix calculé par l'API si disponible
      if (o._calculated_segment_price) {
        price = parseFloat(o._calculated_segment_price);
      }
      // Sinon, si on a un détour précalculé, utiliser le prix ajusté
      else if (isDetour && detourInfo && detourInfo.adjustedPrice) {
        price = parseFloat(detourInfo.adjustedPrice);
      }
    }
    
    priceText = price ? `${(Math.round(price * 2) / 2).toFixed(2).replace('.', ',')} €` : '—';
    
    // Badge détour si applicable - simple et épuré
    const detourBadge = isDetour && detourInfo ? `
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="${this.detourColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="${this.detourColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span style="font-size:13px;font-weight:600;color:${this.detourColor};font-family:${this.fontFamily};">Trajet avec détour</span>
      </div>` : '';
    
    // Formater l'adresse du point de rendez-vous (ville sur une ligne, région en dessous)
    const formatMeetingPointAddress = (address) => {
      if (!address) return '';
      const match = address.match(/^(.+?)\s*\((.+?)\)$/);
      if (match) {
        const [, city, region] = match;
        return `<div style="text-align:center;line-height:1.3;"><div style="white-space:nowrap;">${city.trim()}</div><div style="font-size:0.9em;opacity:0.8;white-space:nowrap;font-family:${this.fontFamily};">(${region.trim()})</div></div>`;
      }
      return address;
    };
    
    // Icônes de places
    let seatIcons = '';
    if (Number.isFinite(Number(seats))) {
      const totalSeats = Number(seats);
      const takenSeats = totalSeats - (remaining != null ? remaining : 0);
      for (let i = 0; i < totalSeats; i++) {
        const taken = i < takenSeats;
        seatIcons += `<span style="display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:4px;${taken ? 'background:#ddd;' : 'background:#4caf50;'}"></span>`;
      }
    }
    
    // Structure de l'itinéraire : différente pour aller (pointillés à gauche) et retour (pointillés à droite)
    let routeTimeline = '';
    
    if (isOutbound) {
      // ALLER : pointillés -> point de rendez-vous -> ligne pleine -> destination
      routeTimeline = `
        <div style="display:flex;align-items:flex-start;margin-bottom:4px;">
          ${isDetour && meetingPointLocation ? `
            <div style="width:80px;flex-shrink:0;" class="detour-info">
              <div style="text-align:left;">
                <div style="font-size:11px;color:${textSecondary};margin-bottom:2px;font-weight:600;font-family:${this.fontFamily};" class="date-text">${departureDate || '—'}</div>
                <div style="font-size:22px;font-weight:700;line-height:1;color:${this.detourColor};font-family:${this.fontFamily};" class="time-text">${departureTime || '—'}</div>
              </div>
            </div>
          ` : `
            <div style="width:80px;flex-shrink:0;">
              <div style="text-align:left;">
                <div style="font-size:11px;color:${textSecondary};margin-bottom:2px;font-weight:600;font-family:${this.fontFamily};" class="date-text">${departureDate || '—'}</div>
                <div style="font-size:22px;font-weight:700;line-height:1;color:${cardColor};font-family:${this.fontFamily};" class="time-text">${departureTime || '—'}</div>
              </div>
            </div>
          `}
          <div style="flex:1;height:4px;background:${cardColor};margin:10px 8px 0 8px;min-width:20px;position:relative;">
            <div style="position:absolute;left:-7px;top:50%;transform:translateY(-50%);width:14px;height:14px;border-radius:50%;background:white;border:3px solid ${cardColor};"></div>
            <div style="position:absolute;right:-7px;top:50%;transform:translateY(-50%);width:14px;height:14px;border-radius:50%;background:white;border:3px solid ${cardColor};"></div>
          </div>
          <div style="width:80px;flex-shrink:0;">
            <div style="text-align:right;">
              <div style="font-size:11px;color:${textSecondary};margin-bottom:2px;font-weight:600;font-family:${this.fontFamily};" class="date-text">${arrivalDate || '—'}</div>
              <div style="font-size:22px;font-weight:700;line-height:1;color:${cardColor};font-family:${this.fontFamily};" class="time-text">${arrivalTime || '—'}</div>
            </div>
          </div>
        </div>
        <div style="display:flex;align-items:flex-start;font-size:11px;color:${textSecondary};font-weight:500;margin-bottom:8px;font-family:${this.fontFamily};" class="address-row">
          <div style="width:80px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-height:16px;">
            <button class="btn-show-departure-map" data-offer-id="${offerId}" data-trip-type="${tripType}" style="border:none;background:transparent;color:${cardColor};text-decoration:none;cursor:pointer;padding:0;font-weight:500;font-family:inherit;">📍 ${isDetour && meetingPointLocation && meetingPointLocation !== 'Votre position' ? meetingPointLocation.replace(/<[^>]*>/g, '').replace(/\([^)]*\)/g, '').trim() : startLocation}</button>
          </div>
          <div style="flex:1;margin:0 8px;"></div>
          <div style="width:80px;flex-shrink:0;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-height:16px;">
            <button class="btn-show-arrival-map" data-offer-id="${offerId}" data-trip-type="${tripType}" style="border:none;background:transparent;color:${cardColor};text-decoration:none;cursor:pointer;padding:0;font-weight:500;font-family:inherit;">📍 ${endLocation}</button>
          </div>
        </div>
      `;
    } else {
      // RETOUR : destination (événement) -> ligne pleine -> point de rendez-vous -> pointillés
      routeTimeline = `
        <div style="display:flex;align-items:flex-start;margin-bottom:4px;">
          <div style="width:80px;flex-shrink:0;">
            <div style="text-align:left;">
              <div style="font-size:11px;color:${textSecondary};margin-bottom:2px;font-weight:600;font-family:${this.fontFamily};">${departureDate || '—'}</div>
              <div style="font-size:22px;font-weight:700;line-height:1;color:${cardColor};font-family:${this.fontFamily};">${departureTime || '—'}</div>
            </div>
          </div>
          <div style="flex:1;height:4px;background:${cardColor};margin:10px 8px 0 8px;min-width:20px;position:relative;">
            <div style="position:absolute;left:-7px;top:50%;transform:translateY(-50%);width:14px;height:14px;border-radius:50%;background:white;border:3px solid ${cardColor};"></div>
            <div style="position:absolute;right:-7px;top:50%;transform:translateY(-50%);width:14px;height:14px;border-radius:50%;background:white;border:3px solid ${cardColor};"></div>
          </div>
          ${isDetour && meetingPointLocation ? `
            <div style="width:80px;flex-shrink:0;">
              <div style="text-align:right;">
                <div style="font-size:11px;color:${textSecondary};margin-bottom:2px;font-weight:600;font-family:${this.fontFamily};">${arrivalDate || '—'}</div>
                <div style="font-size:22px;font-weight:700;line-height:1;color:${this.detourColor};font-family:${this.fontFamily};">${arrivalTime || '—'}</div>
              </div>
            </div>
          ` : `
            <div style="width:80px;flex-shrink:0;">
              <div style="text-align:right;">
                <div style="font-size:11px;color:${textSecondary};margin-bottom:2px;font-weight:600;font-family:${this.fontFamily};">${arrivalDate || '—'}</div>
                <div style="font-size:22px;font-weight:700;line-height:1;color:${cardColor};font-family:${this.fontFamily};">${arrivalTime || '—'}</div>
              </div>
            </div>
          `}
        </div>
        <div style="display:flex;align-items:flex-start;font-size:11px;color:${textSecondary};font-weight:500;margin-bottom:8px;font-family:${this.fontFamily};">
          <div style="width:80px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-height:16px;">
            <button class="btn-show-departure-map" data-offer-id="${offerId}" data-trip-type="${tripType}" style="border:none;background:transparent;color:${cardColor};text-decoration:none;cursor:pointer;padding:0;font-weight:500;font-family:inherit;">📍 ${startLocation}</button>
          </div>
          <div style="flex:1;margin:0 8px;"></div>
          <div style="width:80px;flex-shrink:0;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-height:16px;">
            <button class="btn-show-arrival-map" data-offer-id="${offerId}" data-trip-type="${tripType}" style="border:none;background:transparent;color:${cardColor};text-decoration:none;cursor:pointer;padding:0;font-weight:500;font-family:inherit;">📍 ${isDetour && meetingPointLocation && meetingPointLocation !== 'Votre position' ? meetingPointLocation.replace(/<[^>]*>/g, '').replace(/\([^)]*\)/g, '').trim() : endLocation}</button>
          </div>
        </div>
      `;
    }
    
    // Vérifier si cette offre est l'offre sélectionnée
    const isSelected = (isOutbound && this.selectedOutboundOffer && this.selectedOutboundOffer.id === offerId) ||
                       (!isOutbound && this.selectedReturnOffer && this.selectedReturnOffer.id === offerId);
    
    // Vérifier si le même conducteur propose un trajet dans l'autre direction ET qu'on l'a déjà sélectionné
    const sameDriverOtherTrip = isOutbound 
      ? (this.selectedReturnOffer && this.selectedReturnOffer.user_id === uid) // On est sur l'aller, conducteur sélectionné pour le retour
      : (this.selectedOutboundOffer && this.selectedOutboundOffer.user_id === uid); // On est sur le retour, conducteur sélectionné pour l'aller
    
    // Vérifier si ce conducteur propose aussi l'autre trajet (retour si on est sur l'aller, ou vice-versa)
    const offersOtherTrip = isOutbound 
      ? (details.returnTrip?.enabled) // On est sur l'aller, ce conducteur propose aussi un retour
      : (true); // On est sur le retour, donc forcément il propose aussi l'aller
    
    // Appliquer une bordure colorée si : même conducteur + a sélectionné l'autre trajet + propose aussi ce trajet
    const shouldHighlightBorder = sameDriverOtherTrip && offersOtherTrip;
    
    // Calculer la couleur lighter pour le fond sélectionné (80% vers le blanc)
    const hex = cardColor.replace('#', '');
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    const lighterBg = `rgb(${Math.round(r + (255 - r) * 0.8)}, ${Math.round(g + (255 - g) * 0.8)}, ${Math.round(b + (255 - b) * 0.8)})`;
    
    // Style de la carte selon si elle est sélectionnée
    const cardStyleBg = isSelected 
      ? `background:${lighterBg};` 
      : `background:${cardBg};`;
    const cardBorderStyle = isSelected 
      ? `border:3px solid ${cardColor};border-top-width:32px;` 
      : (shouldHighlightBorder 
        ? `border:3px solid ${cardColor};` 
        : `border:none;`);
    
    // Shadow : bien visible par défaut, encore plus marquée quand sélectionnée
    const cardShadow = isSelected
      ? `box-shadow:0 6px 24px rgba(0,0,0,0.15);`
      : `box-shadow:0 4px 16px rgba(0,0,0,0.12);`;
    
    // Texte du bouton selon si elle est sélectionnée
    const buttonText = isOwner ? 'Votre offre' : (full ? 'Complet' : (isSelected ? 'Annuler la sélection' : 'Choisir'));
    const buttonClass = isSelected ? 'btn-choose-offer btn-cancel-selection' : 'btn-choose-offer';
    
    // Bandeau "Votre aller" / "Votre retour" pour les cartes sélectionnées
    const selectionBanner = isSelected 
      ? `<div style="position:absolute;top:-28px;left:8px;font-size:14px;font-weight:700;color:white;text-transform:uppercase;letter-spacing:0.5px;font-family:${this.fontFamily};">${isOutbound ? 'Votre aller' : 'Votre retour'}</div>` 
      : '';
    
    // Bouton d'action : icône à droite pour compacité
    const actionButton = (full || isOwner || insufficientSeats) 
      ? `<div style="display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:50%;background:#eee;color:#999;cursor:not-allowed;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
            <path d="M15 9l-6 6m0-6l6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>`
      : (isSelected 
        ? `<button class="${buttonClass}" data-offer-id="${offerId}" data-trip-type="${tripType}" style="display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:50%;background:#ff3b30;color:#fff;border:none;cursor:pointer;box-shadow:0 2px 8px rgba(255,59,48,0.3);transition:all 0.2s;" title="Annuler la sélection">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
          </button>`
        : `<button class="${buttonClass}" data-offer-id="${offerId}" data-trip-type="${tripType}" style="display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:50%;background:${cardColor};color:#fff;border:none;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,0.15);transition:all 0.2s;" title="Choisir ce trajet">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M5 12l5 5L20 7" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>`
      );
    
    // Message overlay si insuffisant de places
    const insufficientSeatsOverlay = insufficientSeats && !isOwner ? `
      <div style="position:absolute;inset:0;background:rgba(255,255,255,0.85);backdrop-filter:blur(2px);border-radius:12px;display:flex;align-items:center;justify-content:center;z-index:10;pointer-events:none;">
        <div style="background:#fff;padding:16px 24px;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.15);text-align:center;">
          <div style="font-size:15px;font-weight:700;color:#666;margin-bottom:4px;font-family:${this.fontFamily};">Places insuffisantes</div>
          <div style="font-size:13px;color:#999;font-family:${this.fontFamily};">${remaining} ${remaining > 1 ? 'places restantes' : 'place restante'}</div>
        </div>
      </div>
    ` : '';
    
    // Appliquer le style grisé si insuffisant de places
    const cardOpacity = insufficientSeats && !isOwner ? 'opacity:0.5;' : '';
    
    return `<div class="offer-card ${isSelected ? 'selected' : ''}" data-offer-id="${offerId}" data-trip-type="${tripType}" style="position:relative;display:flex;gap:12px;padding:16px;${cardBorderStyle}${cardStyleBg}border-radius:12px;${cardShadow}margin-bottom:12px;transition:all 0.25s cubic-bezier(0.4, 0, 0.2, 1);cursor:${insufficientSeats && !isOwner ? 'not-allowed' : 'pointer'};${cardOpacity}">
      ${selectionBanner}
      
      <div style="flex:1;min-width:0;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
          <div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0;">
            ${avatarHtml}
            <div style="flex:1;min-width:0;">
              <div style="font-size:15px;font-weight:700;color:${textPrimary};display:flex;align-items:center;flex-wrap:wrap;gap:4px;font-family:${this.fontFamily};">
                <span>${driverName}</span>${isDetour && detourInfo ? `<span style="font-size:12px;font-weight:600;color:${this.detourColor};white-space:nowrap;font-family:${this.fontFamily};">peut te ${isOutbound ? 'récupérer' : 'déposer'} en chemin !</span>` : ''}
              </div>
            </div>
          </div>
          <div style="font-size:11px;color:${textSecondary};display:flex;gap:2px;flex-wrap:wrap;font-family:${this.fontFamily};">${seatIcons}</div>
        </div>
        
        <div style="display:flex;align-items:stretch;gap:8px;flex-wrap:wrap;">
          <div style="flex:1;min-width:0;max-width:100%;padding:12px;background:${cardBg};border-radius:8px;border:1px solid ${borderLight};overflow:hidden;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:8px;flex-wrap:wrap;">
              <span style="font-size:13px;font-weight:600;color:${cardColor};white-space:nowrap;font-family:${this.fontFamily};">${cardLabel}${durationStr ? ` (${durationStr})` : ''}</span>
              <span style="font-size:22px;font-weight:800;color:${isDetour && meetingPointLocation ? this.detourColor : cardColor};font-family:${this.fontFamily};">${priceText}</span>
            </div>
            
            ${routeTimeline}
            
          </div>
          
          <div style="display:flex;align-items:center;justify-content:center;min-width:48px;">
            ${actionButton}
          </div>
        </div>
      </div>
      
      ${insufficientSeatsOverlay}
    </div>`;
  }).join('');
    
    inner.innerHTML = pageHeader + cardsHtml;
    
    this.installOfferListHandlers();
    if (!this.applyOwnerStateToOfferCards()) this.scheduleOwnerStateRecheck();
    
    // Handler pour le bouton Valider
    const validateBtn = this.shadowRoot.getElementById('validate-booking-btn');
    if (validateBtn) {
      validateBtn.addEventListener('click', async () => {
        if (hasOutbound && hasReturn) {
          // Réserver les deux : d'abord l'aller, puis le retour
          await this.reserveBothTrips(this.selectedOutboundOffer, this.selectedReturnOffer);
        } else if (hasOutbound) {
          // Réserver uniquement l'aller
          this.showReservationPopup(this.selectedOutboundOffer, 'outbound');
        } else if (hasReturn) {
          // Réserver uniquement le retour
          this.showReservationPopup(this.selectedReturnOffer, 'return');
        }
      });
    }
  }

  getCurrentUserId() {
    try { return (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null; } catch(_) { return null; }
  }

  applyOwnerStateToOfferCards() {
    const uid = this.getCurrentUserId();
    if (!uid) return false;
    try {
      const offers = Array.isArray(this._offers) ? this._offers : [];
      for (const o of offers) {
        if (!o || o.user_id == null) continue;
        if (String(o.user_id) !== uid) continue;
        const offerId = o.id != null ? String(o.id) : null;
        if (!offerId) continue;
        const btn = this.shadowRoot.querySelector(`button.btn-reserve[data-reserve-offer-id="${offerId}"]`);
        if (btn) {
          btn.textContent = 'Votre offre';
          btn.setAttribute('disabled', '');
        }
      }
      return true;
    } catch(_) { return false; }
  }

  scheduleOwnerStateRecheck() {
    this._ownerStateRetries = (this._ownerStateRetries || 0);
    if (this._ownerStateRetries > 8) return; // ~8 * 400ms = 3.2s max
    clearTimeout(this._ownerRecheckTimer);
    this._ownerRecheckTimer = setTimeout(() => {
      this._ownerStateRetries++;
      if (!this.applyOwnerStateToOfferCards()) this.scheduleOwnerStateRecheck();
      else this._ownerStateRetries = 0;
    }, 400);
  }
  installOfferListHandlers() {
    const inner = this.shadowRoot.getElementById('find-offers-inner');
    if (!inner) return;
    this.attachOfferListHandlersToContainer(inner);
    inner._handlersInstalled = true;
  }

  attachOfferListHandlersToContainer(container) {
    if (!container || container._handlersInstalled) return;
    container.addEventListener('click', (e) => {
      // Cancel my offer
      const cancelOfferBtn = e.target.closest('button.btn-cancel-offer');
      if (cancelOfferBtn) {
        e.stopPropagation();
        const offerId = cancelOfferBtn.closest('.offer-card')?.dataset?.offerId || cancelOfferBtn.dataset.offerId;
        if (offerId) this.cancelMyOffer(String(offerId));
        return;
      }
      // Cancel my reservation
      const cancelResBtn = e.target.closest('button.btn-cancel-reservation');
      if (cancelResBtn) {
        e.stopPropagation();
        const offerId = cancelResBtn.closest('.offer-card')?.dataset?.offerId || cancelResBtn.dataset.offerId;
        if (offerId) this.cancelMyReservation(String(offerId));
        return;
      }
      // Confirm a passenger reservation (driver)
      const confirmBtn = e.target.closest('button.btn-confirm-reservation');
      if (confirmBtn) {
        e.stopPropagation();
        const offerId = confirmBtn.dataset.offerId || confirmBtn.closest('.offer-card')?.dataset?.offerId;
        const passengerId = confirmBtn.dataset.passengerId;
        const tripType = confirmBtn.dataset.tripType || 'outbound';
        if (offerId && passengerId) this.confirmReservation(String(offerId), String(passengerId), tripType);
        return;
      }
      // Reject/cancel a passenger reservation (driver)
      const rejectBtn = e.target.closest('button.btn-reject-reservation');
      if (rejectBtn) {
        e.stopPropagation();
        const offerId = rejectBtn.dataset.offerId || rejectBtn.closest('.offer-card')?.dataset?.offerId;
        const passengerId = rejectBtn.dataset.passengerId;
        const tripType = rejectBtn.dataset.tripType || 'outbound';
        if (offerId && passengerId) this.driverRejectReservation(String(offerId), String(passengerId), tripType);
        return;
      }
      // Voir l'itinéraire dans "Mes trajets"
      const viewRouteBtn = e.target.closest('button.btn-view-my-trip-route');
      if (viewRouteBtn) {
        e.stopPropagation();
        const offerId = viewRouteBtn.dataset.offerId || viewRouteBtn.closest('.offer-card')?.dataset?.offerId;
        const mode = viewRouteBtn.dataset.mode; // 'mine-offers' ou 'mine-reservations'
        const tripType = viewRouteBtn.dataset.tripType || 'outbound'; // 'outbound' ou 'return'
        if (offerId) this.showMyTripRoute(String(offerId), mode, tripType);
        return;
      }
      // Onglet "Aller" (Find tab)
      const tabOutboundBtn = e.target.closest('#find-tab-outbound');
      if (tabOutboundBtn) {
        e.stopPropagation();
        this.findSearchPage = 'outbound';
        if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
        return;
      }
      // Onglet "Retour" (Find tab)
      const tabReturnBtn = e.target.closest('#find-tab-return');
      if (tabReturnBtn) {
        e.stopPropagation();
        this.findSearchPage = 'return';
        if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
        return;
      }
      // Bouton "Choisir" (Find tab)
      const chooseBtn = e.target.closest('button.btn-choose-offer');
      if (chooseBtn) {
        e.stopPropagation();
        const offerId = chooseBtn.dataset.offerId;
        const tripType = chooseBtn.dataset.tripType;
        const offer = (this._offers || []).find(o => String(o.id) === String(offerId));
        if (offer) {
          console.log('🔘 Bouton Choisir cliqué - offerId:', offerId, 'tripType:', tripType);
          console.log('📦 selectedOutboundOffer:', this.selectedOutboundOffer);
          
          // Si c'est un bouton "Annuler la sélection", désélectionner
          if (chooseBtn.classList.contains('btn-cancel-selection')) {
            if (tripType === 'outbound') {
              this.selectedOutboundOffer = null;
            } else if (tripType === 'return') {
              this.selectedReturnOffer = null;
            }
            // Re-render pour mettre à jour l'affichage
            if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
            return;
          }
          
          // PRIORITÉ 1 : Si c'est un retour et qu'un aller du même conducteur a été sélectionné avec un détour
          // Les deux trajets (aller/retour) ont le MÊME id d'offre, seul le tripType diffère
          // IMPORTANT: Ne s'applique QUE si l'utilisateur a explicitement sélectionné un aller avant
          if (tripType === 'return' && 
              this.selectedOutboundOffer && 
              String(this.selectedOutboundOffer.id) === String(offerId) && 
              this.selectedOutboundOffer._detourInfo) {
            // Utiliser le même point de rendez-vous pour le retour
            const detourInfo = this.selectedOutboundOffer._detourInfo;
            const meetingAddress = detourInfo.meetingAddress || 'Point de rendez-vous';
            
            console.log('🔄 Return trip from same driver with detour already selected');
            console.log('Meeting point:', meetingAddress);
            
            // Copier les infos de détour pour le retour sans afficher de popup
            offer._detourInfo = {...detourInfo};
            this.selectedReturnOffer = offer;
            // Re-render pour afficher la sélection et le bouton de validation
            if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
            return;
          }
          
          // PRIORITÉ 1 BIS : Si c'est un aller et qu'un retour du même conducteur a été sélectionné avec un détour
          // Utiliser le même point de rendez-vous pour l'aller
          if (tripType === 'outbound' && 
              this.selectedReturnOffer && 
              String(this.selectedReturnOffer.id) === String(offerId) && 
              this.selectedReturnOffer._detourInfo) {
            // Utiliser le même point de rendez-vous pour l'aller
            const detourInfo = this.selectedReturnOffer._detourInfo;
            const meetingAddress = detourInfo.meetingAddress || 'Point de rendez-vous';
            
            console.log('🔄 Outbound trip from same driver with detour already selected (return first)');
            console.log('Meeting point:', meetingAddress);
            
            // Copier les infos de détour pour l'aller sans afficher de popup
            offer._detourInfo = {...detourInfo};
            this.selectedOutboundOffer = offer;
            // Re-render pour afficher la sélection et le bouton de validation
            if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
            return;
          }
          
          // PRIORITÉ 2 : Vérifier si l'offre nécessite une sélection de point de rencontre
          // (accept_passengers_on_route = true ET point de départ hors du rayon)
          // Pour carette : par défaut tous les trajets acceptent les passagers en route
          const acceptsPassengers = offer.accept_passengers_on_route !== false; // true par défaut
          const needsSelection = acceptsPassengers
            && this.searchCenterCoords 
            && !offer._noDetourNeeded 
            && !offer._incompatible;
          
          console.log('🎯 Vérification sélection point de rencontre:', {
            offerId: offer.id,
            accept_passengers_on_route: offer.accept_passengers_on_route,
            acceptsPassengers,
            hasSearchCenter: !!this.searchCenterCoords,
            noDetourNeeded: offer._noDetourNeeded,
            incompatible: offer._incompatible,
            needsSelection
          });
          
          if (needsSelection) {
            // Ouvrir la carte pour sélectionner le point de rencontre
            this.showRouteModal(offer, tripType);
          } else {
            // Pas de sélection nécessaire, juste sélectionner l'offre
            if (tripType === 'outbound') {
              this.selectedOutboundOffer = offer;
              // Ne plus passer automatiquement à la page retour
              // Re-render pour afficher la sélection et le bouton de réservation
              if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
            } else if (tripType === 'return') {
              this.selectedReturnOffer = offer;
              // Re-render pour afficher la sélection et le bouton de réservation
              if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
            }
          }
        }
        return;
      }
      // Bouton "Voir le départ sur la carte"
      const showDepartureBtn = e.target.closest('button.btn-show-departure-map');
      if (showDepartureBtn) {
        e.stopPropagation();
        const offerId = showDepartureBtn.dataset.offerId;
        const tripType = showDepartureBtn.dataset.tripType;
        const offer = (this._offers || []).find(o => String(o.id) === String(offerId));
        if (offer) {
          this.showDepartureMapModal(offer, tripType);
        }
        return;
      }
      // Bouton "Voir l'arrivée sur la carte"
      const showArrivalBtn = e.target.closest('button.btn-show-arrival-map');
      if (showArrivalBtn) {
        e.stopPropagation();
        const offerId = showArrivalBtn.dataset.offerId;
        const tripType = showArrivalBtn.dataset.tripType;
        const offer = (this._offers || []).find(o => String(o.id) === String(offerId));
        if (offer) {
          this.showArrivalMapModal(offer, tripType);
        }
        return;
      }
      const showMeetingBtn = e.target.closest('button.btn-show-meeting-point-map');
      if (showMeetingBtn) {
        e.stopPropagation();
        const offerId = showMeetingBtn.dataset.offerId;
        const tripType = showMeetingBtn.dataset.tripType;
        const offer = (this._offers || []).find(o => String(o.id) === String(offerId));
        if (offer) {
          this.showMeetingPointMapModal(offer, tripType);
        }
        return;
      }
      const reserveBtn = e.target.closest('button.btn-reserve');
      if (reserveBtn) {
        e.stopPropagation();
        const offerId = reserveBtn.dataset.reserveOfferId;
        const offer = (this._offers || []).find(o => String(o.id) === String(offerId));
        if (offer) this.showReservationPopup(offer);
        return;
      }
      const card = e.target.closest('.offer-card');
      if (card) {
        const offerId = card.dataset.offerId;
        const offer = (this._offers || []).find(o => String(o.id) === String(offerId));
        if (offer) this.selectOfferAndDrawRoute(card, offer);
      }
    });
    container._handlersInstalled = true;
  }

  async cancelMyOffer(offerId) {
    try {
      const uid = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
      if (!uid) { alert('Veuillez vous connecter.'); return; }
      if (!confirm('Annuler cette offre de covoit ?')) return;
      const res = await fetch(`/api/carpool/${encodeURIComponent(offerId)}?user_id=${encodeURIComponent(uid)}`, { method:'DELETE', credentials:'include' });
      if (!res.ok) {
        const tx = await res.text().catch(()=> '');
        alert("Annulation impossible: " + (tx || res.status));
        return;
      }
      // Refresh lists
      await this.fetchMyTrips();
      // Optionally refresh global offers
      try { await this.fetchCarpoolOffers(true); } catch(_) {}
    } catch(e) { alert('Erreur pendant l\'annulation.'); }
  }

  async cancelMyReservation(offerId) {
    try {
      const uid = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
      if (!uid) { alert('Veuillez vous connecter.'); return; }
      if (!confirm('Annuler votre réservation ?')) return;
      const res = await fetch(`/api/carpool/reservations/${encodeURIComponent(offerId)}?user_id=${encodeURIComponent(uid)}`, { method:'DELETE', credentials:'include' });
      if (!res.ok) {
        const tx = await res.text().catch(()=> '');
        alert("Annulation impossible: " + (tx || res.status));
        return;
      }
      await this.fetchMyTrips();
      try { await this.fetchCarpoolOffers(true); } catch(_) {}
    } catch(e) { alert('Erreur pendant l\'annulation.'); }
  }
  async confirmReservation(offerId, passengerId, tripType = 'outbound') {
    try {
      const uid = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
      if (!uid) { alert('Veuillez vous connecter.'); return; }
      
      const tripLabel = tripType === 'outbound' ? "l'aller" : "le retour";
      
      // Message explicite sur les conséquences de la confirmation
      const confirmed = confirm(
        `⚠️ En acceptant ce détour pour ${tripLabel} :\n\n` +
        '• Votre itinéraire sera modifié\n' +
        '• Votre heure de départ sera reculée\n' +
        '• Votre temps disponible pour d\'autres détours sera réduit\n' +
        '• Les autres passagers (si présents) verront leurs horaires ajustés\n\n' +
        'Confirmez-vous l\'acceptation de ce détour ?'
      );
      
      if (!confirmed) return;
      
      const res = await fetch(`/api/carpool/reservations/${encodeURIComponent(offerId)}/confirm?user_id=${encodeURIComponent(uid)}`, {
        method:'POST',
        credentials:'include',
        headers: { 'Content-Type':'application/json' },
        body: JSON.stringify({ 
          passenger_id: String(passengerId),
          trip_type: tripType
        })
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const errorMsg = errorData.error || `Erreur ${res.status}`;
        alert(`Confirmation impossible: ${errorMsg}`);
        return;
      }
      
      // Récupérer les données mises à jour de l'offre
      const result = await res.json();
      
      // Recharger les données AVANT d'afficher le message
      await this.fetchMyTrips();
      
      // Message de succès avec informations sur les changements
      if (result.offer && result.offer.current_departure_time) {
        const newDepartureTime = new Date(result.offer.current_departure_time).toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'});
        const timeUsed = result.offer.time_budget_used || 0;
        const timeRemaining = (result.offer.max_detour_time || 25) - timeUsed;
        
        alert(
          `✅ Détour accepté !\n\n` +
          `🕐 Nouvelle heure de départ : ${newDepartureTime}\n` +
          `⏱️ Temps de détour utilisé : ${timeUsed} min\n` +
          `🔋 Temps restant pour d'autres passagers : ${timeRemaining} min`
        );
      } else {
        alert('✅ Détour accepté ! Votre itinéraire a été mis à jour.');
      }
      try { await this.fetchCarpoolOffers(true); } catch(_) {}
    } catch(e) { 
      console.error('Erreur confirmation:', e);
      alert('Erreur pendant la confirmation.'); 
    }
  }
  
  async driverRejectReservation(offerId, passengerId, tripType = 'outbound') {
    try {
      const uid = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
      if (!uid) { alert('Veuillez vous connecter.'); return; }
      
      const tripLabel = tripType === 'outbound' ? "l'aller" : "le retour";
      
      const confirmed = confirm(
        `⚠️ En annulant cette réservation pour ${tripLabel} :\n\n` +
        '• Votre itinéraire sera recalculé sans ce passager\n' +
        '• Votre heure de départ sera ajustée\n' +
        '• Les autres passagers (si présents) verront leurs horaires modifiés\n' +
        '• Votre temps disponible pour de nouveaux détours augmentera\n\n' +
        'Confirmez-vous l\'annulation ?'
      );
      
      if (!confirmed) return;
      
      const res = await fetch(`/api/carpool/reservations/${encodeURIComponent(offerId)}/passenger/${encodeURIComponent(passengerId)}?user_id=${encodeURIComponent(uid)}&trip_type=${encodeURIComponent(tripType)}`, {
        method:'DELETE',
        credentials:'include'
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const errorMsg = errorData.error || `Erreur ${res.status}`;
        
        // Message plus convivial selon le type d'erreur
        if (res.status === 503 || errorMsg.includes('temporairement indisponible')) {
          alert('⚠️ Le service de calcul d\'itinéraire est temporairement indisponible.\n\nVeuillez réessayer dans quelques instants (30 secondes à 1 minute).');
        } else {
          alert(`Annulation impossible: ${errorMsg}`);
        }
        return;
      }
      
      // Récupérer les données mises à jour
      const result = await res.json();
      
      // Recharger les données AVANT d'afficher le message
      await this.fetchMyTrips();
      
      // Message de succès
      if (result.offer) {
        const hasRemainingReservations = result.reservations && result.reservations.length > 0;
        
        if (hasRemainingReservations) {
          const timeUsed = result.offer.time_budget_used || 0;
          const timeRemaining = (result.offer.max_detour_time || 25) - timeUsed;
          alert(
            `✅ Réservation annulée !\n\n` +
            `L'itinéraire a été recalculé.\n` +
            `⏱️ Temps de détour utilisé : ${timeUsed} min\n` +
            `🔋 Temps disponible : ${timeRemaining} min`
          );
        } else {
          alert('✅ Réservation annulée ! Retour à votre itinéraire original.');
        }
      } else {
        alert('✅ Réservation annulée.');
      }
      try { await this.fetchCarpoolOffers(true); } catch(_) {}
    } catch(e) {
      console.error('Erreur annulation:', e);
      alert('Erreur pendant l\'annulation.');
    }
  }

  async showMyTripRoute(offerId, mode, tripType = 'outbound') {
    try {
      console.log('🗺️ showMyTripRoute:', { offerId, mode, tripType });
      
      // Charger le détail complet de l'offre avec les routes et les passagers
      const [detailResponse, reservationsResponse] = await Promise.all([
        fetch(`/api/carpool/${offerId}`),
        mode === 'mine-offers' ? fetch(`/api/carpool/reservations/by-offers?ids=${offerId}`) : Promise.resolve(null)
      ]);
      
      if (!detailResponse.ok) {
        alert('Impossible de charger les détails du trajet');
        return;
      }
      
      const detail = await detailResponse.json();
      const reservationsData = reservationsResponse?.ok ? await reservationsResponse.json() : null;
      
      // Filtrer les passagers selon le trip_type
      const allPassengers = reservationsData?.reservations?.[offerId] || [];
      const passengers = allPassengers.filter(p => p.trip_type === tripType);
      
      // Afficher le conteneur de la carte
      const mapContainer = this.shadowRoot.getElementById('my-trips-map-container');
      const mapDiv = this.shadowRoot.getElementById('my-trips-map');
      const timelineDiv = this.shadowRoot.getElementById('my-trips-timeline');
      
      if (!mapContainer || !mapDiv || !timelineDiv) return;
      
      mapContainer.style.display = 'block';
      
      // Initialiser la carte si ce n'est pas déjà fait
      if (!this.myTripsMap) {
        const isDark = this.getAttribute('theme') === 'dark';
        const mapStyle = isDark 
          ? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          : "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
        
        this.myTripsMap = new maplibregl.Map({
          container: mapDiv,
          style: mapStyle,
          center: [2.3522, 48.8566],
          zoom: 10
        });
        
        this.myTripsMap.addControl(new maplibregl.NavigationControl());
        
        // Bouton fermer
        const closeBtn = this.shadowRoot.getElementById('close-my-trips-map');
        if (closeBtn) {
          closeBtn.onclick = () => {
            mapContainer.style.display = 'none';
          };
        }
      }
      
      // Attendre que la carte soit chargée avant d'ajouter les sources
      const drawRoute = () => {
        // Nettoyer les couches précédentes
        ['my-trip-route', 'my-trip-base', 'my-trip-detours', 'my-trip-markers'].forEach(id => {
          if (this.myTripsMap.getLayer(id)) this.myTripsMap.removeLayer(id);
          if (this.myTripsMap.getSource(id)) this.myTripsMap.removeSource(id);
        });
        
        // Sélectionner la bonne route selon trip_type
        let baseRoute, currentRoute;
        
        if (tripType === 'return') {
          // Route RETOUR
          // La route de base est la route retour originale (sans détours)
          baseRoute = detail.route_return?.geometry || detail.route_return;
          
          // Route actuelle retour : 
          // - Vérifier s'il y a des réservations confirmées pour le retour
          // - Si oui, le backend a recalculé route_return avec les détours
          // - Sinon, utiliser route_return originale
          const hasReturnReservations = detail.reservations?.some(r => 
            r.trip_type === 'return' && r.status === 'confirmed'
          );
          
          console.log(`🔍 Return trip - hasReturnReservations: ${hasReturnReservations}`);
          
          // Si pas de réservations confirmées pour le retour, pas de détours
          // Donc currentRoute = baseRoute
          if (hasReturnReservations) {
            // Le backend a mis à jour route_return avec les détours
            currentRoute = detail.route_return;
          } else {
            // Pas de détours, route originale
            currentRoute = baseRoute;
          }
        } else {
          // Route ALLER
          baseRoute = detail.route_outbound?.geometry || detail.route_outbound;
          // Route actuelle aller (current_route_geometry avec détours ou route_outbound sans)
          currentRoute = detail.current_route_geometry || detail.route_outbound;
        }
        
        // Normaliser le format de currentRoute
        if (currentRoute) {
          // Si c'est un objet avec .geometry, extraire la géométrie
          if (currentRoute.geometry && currentRoute.geometry.coordinates) {
            currentRoute = currentRoute.geometry;
          }
          // Sinon, c'est déjà une géométrie directe
        } else {
          // Fallback sur la route de base
          currentRoute = baseRoute;
        }
        
        console.log('🗺️ Drawing routes:', {
          tripType,
          hasBaseRoute: !!baseRoute,
          hasCurrentRoute: !!currentRoute,
          currentRouteType: typeof currentRoute,
          currentRouteCoords: currentRoute?.coordinates?.length,
          baseRouteCoords: baseRoute?.coordinates?.length,
          routeReturnRaw: detail.route_return,
          currentRouteGeometryRaw: detail.current_route_geometry
        });
        
        if (!currentRoute || !currentRoute.coordinates) {
          alert('Pas d\'itinéraire disponible');
          mapContainer.style.display = 'none';
          return;
        }
        
        // Vérifier s'il y a des détours actifs pour ce trip_type
        const hasDetours = passengers.length > 0;
        console.log(`🔍 ${tripType} - hasDetours: ${hasDetours}, passengers: ${passengers.length}`);
        
        // Si route de base différente ET qu'il y a des détours, l'afficher en gris clair DERRIÈRE
        if (hasDetours && baseRoute && baseRoute.coordinates) {
          this.myTripsMap.addSource('my-trip-base', {
            type: 'geojson',
            data: { type: 'Feature', geometry: baseRoute }
          });
          
          this.myTripsMap.addLayer({
            id: 'my-trip-base',
            type: 'line',
            source: 'my-trip-base',
            paint: {
              'line-color': '#94a3b8',
              'line-width': 3,
              'line-opacity': 0.5,
              'line-dasharray': [4, 2]
            }
          });
          
          console.log('✅ Base route (grise) ajoutée');
        }
        
        // Afficher la route actuelle (avec détours si présents) PAR-DESSUS
        this.myTripsMap.addSource('my-trip-route', {
          type: 'geojson',
          data: { type: 'Feature', geometry: currentRoute }
        });
        
        // Couleur selon trip_type ET présence de détours
        const routeColor = tripType === 'return' 
          ? (hasDetours ? this.detourColor : this.colorReturn)
          : (hasDetours ? this.detourColor : this.colorOutbound);
        
        this.myTripsMap.addLayer({
          id: 'my-trip-route',
          type: 'line',
          source: 'my-trip-route',
          paint: {
            'line-color': routeColor,
            'line-width': 5,
            'line-opacity': 0.9
          }
        });
        
        console.log(`✅ Current route ajoutée, couleur: ${routeColor} (${tripType}, détours: ${hasDetours})`);
        
        // Markers : départ, arrivée, passagers
        const markers = [];
        const details = detail.details || {};
        const fromCoords = details.fromCoords;
        const toCoords = details.toCoords;
      
      if (fromCoords) {
        markers.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: fromCoords },
          properties: { type: 'start', label: 'Départ', time: detail.current_departure_time || detail.datetime }
        });
      }
      
      if (toCoords) {
        markers.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: toCoords },
          properties: { type: 'end', label: 'Arrivée', time: detail.datetime }
        });
      }
      
      // Passagers confirmés
      passengers.filter(p => p.status === 'confirmed').forEach((p, idx) => {
        const coords = p.pickup_coords || p.meeting_point_coords;
        if (coords) {
          const parsedCoords = typeof coords === 'string' ? JSON.parse(coords) : coords;
          markers.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: parsedCoords },
            properties: { 
              type: 'passenger', 
              label: `Passager ${idx + 1}`,
              name: this.getDisplayNameForUid(p.user_id || p.passenger_user_id, p),
              time: p.pickup_time
            }
          });
        }
      });
      
      if (markers.length) {
        this.myTripsMap.addSource('my-trip-markers', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: markers }
        });
        
        this.myTripsMap.addLayer({
          id: 'my-trip-markers',
          type: 'circle',
          source: 'my-trip-markers',
          paint: {
            'circle-radius': 8,
            'circle-color': [
              'match',
              ['get', 'type'],
              'start', '#22c55e',
              'end', '#ef4444',
              'passenger', '#f59e0b',
              '#3b82f6'
            ],
            'circle-stroke-width': 2,
            'circle-stroke-color': '#fff'
          }
        });
      }
      
      // Adapter la vue
      const bbox = this.calculateBBox(currentRoute.coordinates);
      if (bbox) {
        this.myTripsMap.fitBounds(bbox, { padding: 50, maxZoom: 14 });
      }
      
      // Timeline avec les heures
      let timelineHtml = '<div style="display:flex;flex-direction:column;gap:12px;">';
      
      if (fromCoords && (detail.current_departure_time || detail.datetime)) {
        const time = this.formatTime(detail.current_departure_time || detail.datetime);
        timelineHtml += `
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:12px;height:12px;border-radius:50%;background:#22c55e;flex-shrink:0;"></div>
            <div style="flex:1;">
              <div style="font-weight:600;font-size:14px;">${details.from || 'Départ'}</div>
              <div style="font-size:13px;color:#6b7280;">${time}</div>
            </div>
          </div>
        `;
      }
      
      passengers.filter(p => p.status === 'confirmed').sort((a, b) => (a.pickup_order || 0) - (b.pickup_order || 0)).forEach(p => {
        const name = this.getDisplayNameForUid(p.user_id || p.passenger_user_id, p);
        const time = p.pickup_time ? this.formatTime(p.pickup_time) : '—';
        const address = p.meeting_point_address || p.pickup_address || p.meeting_address || 'Point de rendez-vous';
        
        timelineHtml += `
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:12px;height:12px;border-radius:50%;background:#f59e0b;flex-shrink:0;"></div>
            <div style="flex:1;">
              <div style="font-weight:600;font-size:14px;">${name}</div>
              <div style="font-size:12px;color:#6b7280;">${address}</div>
              <div style="font-size:13px;color:#6b7280;">${time}</div>
            </div>
          </div>
        `;
      });
      
      if (toCoords) {
        const time = this.formatTime(detail.datetime);
        timelineHtml += `
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:12px;height:12px;border-radius:50%;background:#ef4444;flex-shrink:0;"></div>
            <div style="flex:1;">
              <div style="font-weight:600;font-size:14px;">${details.to || 'Arrivée'}</div>
              <div style="font-size:13px;color:#6b7280;">${time}</div>
            </div>
          </div>
        `;
      }
      
      timelineHtml += '</div>';
      
      // Afficher le bandeau de détours seulement s'il y a des passagers confirmés pour CE trip_type
      if (passengers.length > 0) {
        const timeUsed = detail.time_budget_used || 0;
        const maxTime = detail.max_detour_time || 25;
        timelineHtml += `
          <div style="margin-top:12px;padding:12px;background:#fef3c7;border-radius:8px;border-left:4px solid #f59e0b;">
            <div style="font-size:12px;font-weight:600;color:#92400e;margin-bottom:4px;">⚠️ Itinéraire avec détours</div>
            <div style="font-size:11px;color:#78350f;">Temps de détour : ${timeUsed} min / ${maxTime} min</div>
          </div>
        `;
      }
      
      timelineDiv.innerHTML = timelineHtml;
      }; // Fin de drawRoute()
      
      // Appeler drawRoute() quand la carte est prête
      if (this.myTripsMap.loaded()) {
        drawRoute();
      } else {
        this.myTripsMap.once('load', drawRoute);
      }
      
    } catch(e) {
      console.error('Erreur affichage itinéraire:', e);
      alert('Erreur lors de l\'affichage de l\'itinéraire');
    }
  }

  formatTime(datetime) {
    if (!datetime) return '—';
    try {
      const d = new Date(datetime);
      return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    } catch(e) {
      return '—';
    }
  }

  calculateBBox(coords) {
    if (!coords || coords.length === 0) return null;
    let minLon = Infinity, maxLon = -Infinity;
    let minLat = Infinity, maxLat = -Infinity;
    coords.forEach(c => {
      if (c[0] < minLon) minLon = c[0];
      if (c[0] > maxLon) maxLon = c[0];
      if (c[1] < minLat) minLat = c[1];
      if (c[1] > maxLat) maxLat = c[1];
    });
    return [[minLon, minLat], [maxLon, maxLat]];
  }

  selectOfferAndDrawRoute(cardEl, offer) {
    this.shadowRoot.querySelectorAll('.offer-card.selected').forEach(c => c.classList.remove('selected'));
    cardEl.classList.add('selected');
    this.selectedOfferId = offer.id;
    // En onglet "Mes trajets", on n'affiche pas la carte: ne pas tracer de route
    if (this.activeTab === 'mine') return;
    this.drawSelectedOfferRoute(offer);
  }
  async drawSelectedOfferRoute(offer) {
    try {
      if (!offer || !offer.id) return;
      
      // Charger le détail complet de l'offre avec les routes depuis la base
      const detailResponse = await fetch(`/api/carpool/${offer.id}`);
      if (!detailResponse.ok) {
        console.warn('Impossible de charger les détails de l\'offre');
        return;
      }
      const detail = await detailResponse.json();
      
      // Nettoyer la route précédente
      if (this.map.getSource('selected-offer-route')) {
        if (this.map.getLayer('selected-offer-route-line')) this.map.removeLayer('selected-offer-route-line');
        this.map.removeSource('selected-offer-route');
      }
      
      // Utiliser current_route_geometry (avec détours acceptés) ou fallback sur route_outbound
      const routeGeometry = detail.current_route_geometry || detail.route_outbound?.geometry;
      if (!routeGeometry) {
        console.warn('Pas de route disponible pour cette offre');
        return;
      }
      
      const geo = { type: 'Feature', geometry: routeGeometry };
      this.map.addSource('selected-offer-route', { type: 'geojson', data: geo });
      this.map.addLayer({ 
        id: 'selected-offer-route-line', 
        type: 'line', 
        source: 'selected-offer-route', 
        paint: { 
          'line-color': '#ff6d00', 
          'line-width': 5, 
          'line-opacity': 0.85 
        } 
      });
      
      // Zoomer sur la route
      try {
        const coords = geo.geometry.coordinates;
        if (Array.isArray(coords) && coords.length) {
          const b = new maplibregl.LngLatBounds(coords[0], coords[0]);
          for (let i = 1; i < coords.length; i++) b.extend(coords[i]);
          this.map.fitBounds(b, { padding: 50 });
        }
      } catch(_) {}
    } catch(err) {
      console.error('Erreur lors du chargement de la route:', err);
    }
  }
  async showRouteModal(offer, tripType = 'outbound') {
    this.closeRouteModal();
    
    // Vérifier si c'est une offre avec détour qui nécessite un choix de point
    // Conditions : 
    // 1. L'offre accepte les passagers en route (accept_passengers_on_route != false, true par défaut dans carette)
    // 2. On a une position de recherche du passager (searchCenterCoords existe)
    // 3. Le point de départ/arrivée pertinent est EN DEHORS du rayon de recherche
    //    (sinon le passager peut aller directement au point de RDV fixe)
    
    let needsMeetingPointSelection = false;
    
    // Pour carette : par défaut tous les trajets acceptent les passagers en route
    const acceptsPassengers = offer.accept_passengers_on_route !== false;
    if (acceptsPassengers && this.searchCenterCoords) {
      // Le flag _noDetourNeeded est posé par calculateDetoursForOffers
      // Il indique que le point de départ (aller) ou arrivée (retour) est dans le rayon
      if (offer._noDetourNeeded === true) {
        console.log('✅ No detour needed - relevant point is within search radius');
        needsMeetingPointSelection = false;
      } else if (offer._incompatible === true) {
        console.log('⚠️ Offer incompatible with search location');
        needsMeetingPointSelection = false;
      } else {
        console.log('🎯 Detour needed - meeting point selection enabled');
        needsMeetingPointSelection = true;
      }
    }
    
    console.log('🔍 Final needsMeetingPointSelection?', needsMeetingPointSelection);
    
    // Si un détour est nécessaire, vérifier s'il y a une intersection possible AVANT d'ouvrir la modale
    if (needsMeetingPointSelection && this.searchCenterCoords && this.searchRadiusMeters) {
      const detail = await (await fetch(`/api/carpool/${offer.id}`)).json();
      const routeGeometry = detail.current_route_geometry || detail.route_outbound?.geometry;
      
      if (routeGeometry && routeGeometry.coordinates) {
        // Calculer rapidement s'il y a une intersection
        const projectedIdx = this.findNearestPointOnRoute(this.searchCenterCoords, routeGeometry.coordinates);
        const projectedPoint = routeGeometry.coordinates[projectedIdx];
        
        const detourTimeLeftMin = detail.detour_time_left || detail.max_detour_time || 60;
        // Utiliser la distance/durée de la route actuelle (avec détours) ou fallback sur originale
        const routeDist = detail.route_outbound?.distance || 100000;
        const routeDur = detail.route_outbound?.duration || 3600;
        const avgSpeedKmH = (routeDist / 1000) / (routeDur / 3600) || 80;
        const projectionRadiusKm = avgSpeedKmH * (detourTimeLeftMin / 60) * 0.5 * 0.3;
        const projectionRadiusM = projectionRadiusKm * 1000;
        
        const projectionCircle = this.createCirclePolygon(projectedPoint, projectionRadiusM);
        const searchCircle = this.createCirclePolygon(this.searchCenterCoords, this.searchRadiusMeters);
        
        const intersection = this.calculatePolygonIntersection(projectionCircle.geometry, searchCircle.geometry);
        
        if (!intersection || !intersection.coordinates || intersection.coordinates.length === 0) {
          console.log('❌ No intersection possible - cannot show map');
          this.showToast('⚠️ Aucune zone de rencontre possible avec ce trajet depuis votre position', 'warning');
          return; // Ne pas ouvrir la modale
        }
        
        console.log('✅ Intersection exists - showing map');
      }
    }
    
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal route-modal" role="dialog" aria-modal="true" style="max-width:90vw;width:800px;height:85vh;display:flex;flex-direction:column;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          ${needsMeetingPointSelection ? '<h3 style="margin:0;font-size:16px;font-weight:600;color:#334155;font-family:${this.fontFamily};">Sélection du point de rendez-vous</h3>' : '<div></div>'}
          <button type="button" class="close-route" aria-label="Fermer" style="background:none;border:none;font-size:24px;cursor:pointer;color:#666;line-height:1;padding:0;width:32px;height:32px;font-family:${this.fontFamily};">×</button>
        </div>
        ${needsMeetingPointSelection ? `
        <div style="padding:8px 12px;background:#fef3c7;border-radius:6px;margin-bottom:8px;border:1px solid ${this.detourColorDark};font-size:13px;text-align:center;color:#78350f;font-family:${this.fontFamily};">
          <strong>📍 Cliquez sur la carte (zone verte) pour choisir votre point de rencontre</strong>
        </div>
        ` : ''}
        <div id="route-legend" style="display:none;padding:8px 12px;background:#f8fafc;border-radius:6px;margin-bottom:8px;border:1px solid #e2e8f0;">
          <div style="display:flex;gap:16px;align-items:center;justify-content:center;font-size:12px;font-family:${this.fontFamily};">
            <div style="display:flex;align-items:center;gap:6px;">
              <div style="width:24px;height:4px;background:${this.colorOutbound};border-radius:2px;"></div>
              <span style="font-weight:600;color:#334155;font-family:${this.fontFamily};">Trajet original</span>
            </div>
            <div style="display:flex;align-items:center;gap:6px;">
              <div style="width:24px;height:4px;background:${this.detourColor};border-radius:2px;"></div>
              <span style="font-weight:600;color:${this.detourColorDark};font-family:${this.fontFamily};">Votre détour</span>
            </div>
          </div>
        </div>
        <div id="route-map-container" style="flex:1;border-radius:8px;overflow:hidden;background:#f0f0f0;position:relative;${needsMeetingPointSelection ? 'cursor:crosshair;' : ''}">
          <div id="detour-status-banner" style="display:none;position:absolute;bottom:0;left:0;right:0;padding:16px;background:white;border-top:3px solid #ddd;z-index:1000;box-shadow:0 -4px 12px rgba(0,0,0,0.1);">
            <div id="detour-status-content"></div>
          </div>
        </div>
        ${needsMeetingPointSelection ? `
        <button id="confirm-meeting-point-btn" disabled style="width:100%;padding:14px;margin-top:12px;border:none;border-radius:10px;font-size:16px;font-weight:700;cursor:not-allowed;background:#d1d5db;color:#9ca3af;transition:all 0.2s;font-family:${this.fontFamily};">
          Choisir ce point de rendez-vous
        </button>
        ` : ''}
      </div>`;
    this.shadowRoot.appendChild(backdrop);
    
    const isDark = this.getAttribute('theme') === 'dark';
    const mapStyle = isDark 
      ? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
      : 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
    
    const mapContainer = backdrop.querySelector('#route-map-container');
    const routeMap = new maplibregl.Map({
      container: mapContainer,
      style: mapStyle,
      center: [2.3522, 48.8566],
      zoom: 5,
      pitch: 0
    });
    
    this._routeModal = { backdrop, map: routeMap };
    
    const onKey = (e) => { if (e.key === 'Escape') { this.closeRouteModal(); } };
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) this.closeRouteModal(); });
    backdrop.querySelector('button.close-route').addEventListener('click', () => this.closeRouteModal());
    document.addEventListener('keydown', onKey, { once:true });
    
    // Handler pour le bouton de confirmation du point de rendez-vous
    const confirmBtn = backdrop.querySelector('#confirm-meeting-point-btn');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => {
        // Fermer la modal
        this.closeRouteModal();
        
        // Stocker l'offre sélectionnée selon le tripType
        if (tripType === 'return') {
          this.selectedReturnOffer = offer;
          // Re-render pour mettre à jour l'affichage et le bouton de validation
          if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
        } else {
          this.selectedOutboundOffer = offer;
          // Re-render pour mettre à jour l'affichage et le bouton de validation
          if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
        }
      });
    }
    
    // Load and draw route
    routeMap.on('load', async () => {
      console.log('🗺️ Carte chargée, début affichage route...');
      // Animation d'entrée premium
      routeMap.easeTo({
        zoom: 6,
        pitch: 30,
        duration: 1200,
        easing: (t) => t * (2 - t)
      });
      try {
        console.log('📡 Fetching offer details from /api/carpool/' + offer.id);
        const detailResponse = await fetch(`/api/carpool/${offer.id}`);
        if (!detailResponse.ok) {
          console.error('❌ Failed to fetch offer details:', detailResponse.status);
          return;
        }
        const detail = await detailResponse.json();
        console.log('✅ Offer details received:', detail);
        let routeGeometry = detail.current_route_geometry || detail.route_outbound?.geometry;
        
        // Si pas de géométrie stockée, calculer la route à la volée
        if (!routeGeometry) {
          console.log('⚠️ No stored geometry, calculating route on the fly...');
          
          // Extraire les coordonnées de départ et destination
          const departureCoords = detail.departure_coords ? JSON.parse(detail.departure_coords) : null;
          const destinationCoords = detail.destination_coords ? JSON.parse(detail.destination_coords) : null;
          
          if (!departureCoords || !destinationCoords) {
            console.error('❌ No departure/destination coordinates found');
            return;
          }
          
          // Convertir {lat, lon} en [lon, lat] pour OSRM
          const departureLonLat = [departureCoords.lon, departureCoords.lat];
          const destinationLonLat = [destinationCoords.lon, destinationCoords.lat];
          
          console.log('📍 Calculating route from', departureLonLat, 'to', destinationLonLat);
          
          // Appeler OSRM via le backend
          const routeResult = await this.fetchRoute([departureLonLat, destinationLonLat], { overview: 'full' });
          
          if (!routeResult.success || !routeResult.data?.routes?.[0]?.geometry) {
            console.error('❌ Failed to calculate route');
            return;
          }
          
          routeGeometry = routeResult.data.routes[0].geometry;
          console.log('✅ Route calculated:', routeGeometry);
        }
        
        if (!routeGeometry) {
          console.error('❌ No route geometry available');
          return;
        }
        
        // Normaliser le format de la géométrie
        // Si c'est {geometry: {coordinates: [...]}}, extraire geometry
        if (routeGeometry.geometry && routeGeometry.geometry.coordinates) {
          routeGeometry = routeGeometry.geometry;
        }
        // Si c'est {coordinates: [...]}, c'est déjà bon
        if (!routeGeometry.coordinates) {
          console.error('❌ Format de géométrie invalide:', routeGeometry);
          return;
        }
        
        // Stocker le max_detour_km et le budget temps restant
        this._currentOfferMaxDetour = detail.max_detour_km || 10;
        this._currentOfferDetourTimeLeft = detail.detour_time_left || detail.max_detour_time || 60;
        console.log('Conductor max_detour_km:', this._currentOfferMaxDetour);
        console.log('Conductor detour_time_left:', this._currentOfferDetourTimeLeft, 'minutes');
        
        console.log('Offer data:', offer);
        console.log('Has detour info?', offer._detourCalculated, offer._detourInfo);
        console.log('Route geometry coords:', routeGeometry.coordinates?.length, 'points');
        
        const geo = { type: 'Feature', geometry: routeGeometry };
        const from = { geometry: { coordinates: routeGeometry.coordinates[0] } };
        const to = { geometry: { coordinates: routeGeometry.coordinates[routeGeometry.coordinates.length - 1] } };
        
        // Ne pas afficher le détour précalculé — on montre juste la route originale
        // Le détour sera calculé et affiché uniquement après le clic de l'utilisateur
        
        // Afficher uniquement la route originale (bleu)
        routeMap.addSource('route', { type: 'geojson', data: geo });
        const baseColor = (this.colorOutbound || '#7c3aed').substring(0, 7); // Enlever alpha si présent
        routeMap.addLayer({
          id: 'route-line',
          type: 'line',
          source: 'route',
          paint: {
            'line-color': baseColor,
            'line-width': 5,
            'line-opacity': 0.9
          }
        });
        
        // NE PAS afficher le détour existant - il sera recalculé après le clic
        
        // Afficher la légende si c'est une offre avec détour possible
        if (needsMeetingPointSelection) {
          const legendDiv = this.shadowRoot.getElementById('route-legend');
          if (legendDiv) {
            legendDiv.style.display = 'block';
          }
        }
          
        // Ajouter les marqueurs de départ et d'arrivée
        new maplibregl.Marker({ color: this.colorOutbound }).setLngLat(from.geometry.coordinates).addTo(routeMap);
        new maplibregl.Marker({ color: '#10b981' }).setLngLat(to.geometry.coordinates).addTo(routeMap);
          
        // Afficher la zone tampon du conducteur (si disponible)
        console.log('Detail object keys:', Object.keys(detail));
          
          // Afficher le buffer temporel : calculé à partir du TEMPS restant disponible
          // Ce buffer montre la zone accessible le long de toute la route
          if (needsMeetingPointSelection && routeGeometry && routeGeometry.coordinates) {
            try {
              // Calculer la largeur du buffer basée sur le BUDGET TEMPS restant
              const detourTimeLeftMin = this._currentOfferDetourTimeLeft || detail.max_detour_time || 60;
              // Utiliser la distance/durée de la route actuelle (avec détours) ou originale
              const routeDist = detail.route_outbound?.distance || 100000;
              const routeDur = detail.route_outbound?.duration || 3600;
              const avgSpeedKmH = (routeDist / 1000) / (routeDur / 3600) || 80;
              
              // Formule : largeur_buffer = vitesse_moy × temps_restant × 0.5 (A/R)
              // On prend 0.5 car le conducteur doit faire l'aller ET le retour au point de RDV
              const bufferWidthKm = avgSpeedKmH * (detourTimeLeftMin / 60) * 0.2;
              
              console.log(`🟢 Time-based buffer: ${detourTimeLeftMin}min @ ${avgSpeedKmH.toFixed(0)}km/h = ${bufferWidthKm.toFixed(1)}km width along route`);
              
              const bufferPolygon = this.createBufferAroundRoute(routeGeometry.coordinates, bufferWidthKm);
              
              if (bufferPolygon) {
                // bufferPolygon est déjà un GeoJSON geometry (type + coordinates)
                // Il faut l'envelopper dans un Feature seulement si ce n'est pas déjà le cas
                const bufferFeature = bufferPolygon.type === 'Feature' 
                  ? bufferPolygon 
                  : { type: 'Feature', geometry: bufferPolygon };
                
                routeMap.addSource('geographic-buffer', {
                  type: 'geojson',
                  data: bufferFeature
                });
                
                routeMap.addLayer({
                  id: 'geographic-buffer-fill',
                  type: 'fill',
                  source: 'geographic-buffer',
                  paint: {
                    'fill-color': '#10b981',
                    'fill-opacity': 0.08
                  }
                });
                
                routeMap.addLayer({
                  id: 'geographic-buffer-outline',
                  type: 'line',
                  source: 'geographic-buffer',
                  paint: {
                    'line-color': '#10b981',
                    'line-width': 1,
                    'line-opacity': 0.3,
                    'line-dasharray': [4, 4]
                  }
                });
                console.log('✅ Time-based buffer displayed (green zone along route)');
              }
            } catch(e) {
              console.warn('Error displaying time-based buffer:', e);
            }
          }
          
          // Calculer la zone cliquable : intersection entre cercle vert (autour du projeté sur route) et cercle passager
          let clickableZone = null;
          let hasProjectionZone = false;
          if (needsMeetingPointSelection && this.searchCenterCoords && this.searchRadiusMeters) {
            try {
              console.log('🔍 Calculating projection-based clickable zone...');
              
              // 1. Projeter le point de recherche sur la route
              const projectedIdx = this.findNearestPointOnRoute(this.searchCenterCoords, routeGeometry.coordinates);
              const projectedPoint = routeGeometry.coordinates[projectedIdx];
              console.log('📍 Projected search point onto route at index', projectedIdx, ':', projectedPoint);
              
              // 2. Calculer le rayon temporel basé sur le budget temps restant du conducteur
              // Formule : rayon_km = vitesse_moy × temps_restant × 0.5 (A/R) × 0.3 (tortuosité)
              const detourTimeLeftMin = this._currentOfferDetourTimeLeft || 60;
              // Utiliser la distance/durée de la route actuelle (avec détours) ou originale
              const routeDist = detail.route_outbound?.distance || 100000;
              const routeDur = detail.route_outbound?.duration || 3600;
              const avgSpeedKmH = (routeDist / 1000) / (routeDur / 3600) || 80;
              const projectionRadiusKm = avgSpeedKmH * (detourTimeLeftMin / 60) * 0.5 * 0.3;
              const projectionRadiusM = projectionRadiusKm * 1000;
              const projectionCircle = this.createCirclePolygon(projectedPoint, projectionRadiusM);
              console.log(`🟢 Projection circle: ${projectionRadiusKm.toFixed(1)}km (${detourTimeLeftMin}min @ ${avgSpeedKmH.toFixed(0)}km/h × 0.5 × 0.3) around projected point`);
              
              // 3. Créer le cercle de recherche du passager
              const searchCircle = this.createCirclePolygon(this.searchCenterCoords, this.searchRadiusMeters);
              console.log(`🔵 Search circle: ${(this.searchRadiusMeters/1000).toFixed(1)}km around search center`);
              
              // 4. Calculer l'intersection entre les deux cercles
              const intersection = this.calculatePolygonIntersection(projectionCircle.geometry, searchCircle.geometry);
              
              if (intersection && intersection.coordinates && intersection.coordinates.length > 0) {
                clickableZone = intersection;
                hasProjectionZone = true;
                console.log('✅ Intersection zone calculated successfully');
              } else {
                console.warn('⚠️ No intersection between projection circle and search circle');
              }
            } catch(e) {
              console.error('Error calculating projection-based zone:', e);
            }
          }
          
          if (clickableZone) {
            try {
              console.log('Clickable zone (intersection):', clickableZone);
              
              if (clickableZone && clickableZone.type && clickableZone.coordinates) {
                console.log('Adding clickable intersection zone to map...');
                
                // Stocker la zone pour la validation des clics
                this._displayedValidationZone = clickableZone;
                
                // Afficher la zone en vert (cercle projeté ∩ cercle recherche)
                const zoneColor = '#10b981';
                const zoneName = 'projection-intersection-zone';
                
                routeMap.addSource(zoneName, {
                  type: 'geojson',
                  data: {
                    type: 'Feature',
                    geometry: clickableZone
                  }
                });
                
                routeMap.addLayer({
                  id: `${zoneName}-fill`,
                  type: 'fill',
                  source: zoneName,
                  paint: {
                    'fill-color': zoneColor,
                    'fill-opacity': 0.25
                  }
                });
                
                routeMap.addLayer({
                  id: `${zoneName}-outline`,
                  type: 'line',
                  source: zoneName,
                  paint: {
                    'line-color': zoneColor,
                    'line-width': 3,
                    'line-opacity': 0.8
                  }
                });
                console.log(`✅ Projection intersection zone added to map in ${zoneColor}`);
              } else {
                console.warn('Invalid clickable zone structure:', clickableZone);
              }
            } catch(e) {
              console.warn('Error displaying clickable zone:', e);
            }
          } else {
            console.log('No detour_zone_outbound in detail');
          }
          
          // Afficher le rayon de recherche du passager (si disponible)
          console.log('Search center coords:', this.searchCenterCoords, 'Radius:', this.searchRadiusMeters);
          if (this.searchCenterCoords && this.searchRadiusMeters) {
            try {
              const searchCircleFeature = this.createCirclePolygon(this.searchCenterCoords, this.searchRadiusMeters);
              console.log('Search circle created:', searchCircleFeature);
              
              routeMap.addSource('search-radius', {
                type: 'geojson',
                data: searchCircleFeature  // c'est déjà un Feature complet
              });
              
              routeMap.addLayer({
                id: 'search-radius-fill',
                type: 'fill',
                source: 'search-radius',
                paint: {
                  'fill-color': '#10b981',
                  'fill-opacity': 0.1
                }
              });
              
              routeMap.addLayer({
                id: 'search-radius-outline',
                type: 'line',
                source: 'search-radius',
                paint: {
                  'line-color': '#10b981',
                  'line-width': 2,
                  'line-opacity': 0.5,
                  'line-dasharray': [4, 2]
                }
              });
              
              // Marqueur au centre du rayon de recherche
              new maplibregl.Marker({ color: '#10b981', scale: 0.8 })
                .setLngLat(this.searchCenterCoords)
                .setPopup(new maplibregl.Popup().setHTML('<strong>Votre recherche</strong>'))
                .addTo(routeMap);
              
              // Si on a besoin de choisir un point de rencontre, ajouter l'interaction
              if (needsMeetingPointSelection && hasProjectionZone) {
                console.log('🎯 Setting up interactive meeting point selection');
                
                // Capture du contexte pour utilisation dans les handlers
                const self = this;
                
                // Utiliser la zone d'intersection déjà calculée et affichée sur la carte
                const validationZone = this._displayedValidationZone;
                
                console.log('Validation zone (from displayed intersection):', validationZone);
                
                // Handler pour les clics sur la carte
                let meetingMarker = null;
                
                const onMapClick = async (e) => {
                  const clickedPoint = [e.lngLat.lng, e.lngLat.lat];
                  console.log('Map clicked at:', clickedPoint);
                  
                  // Vérifier que le point est dans la zone de validation (intersection)
                  let isValid = false;
                  
                  if (validationZone && validationZone.type && validationZone.coordinates) {
                    isValid = self.pointInPolygon(clickedPoint, validationZone.coordinates[0]);
                    console.log('Point in validation zone (intersection)?', isValid);
                  }
                  
                  if (!isValid) {
                    self.showToast('⚠️ Choisissez un point dans la zone violette', 'warning');
                    return;
                  }
                  
                  // Point valide ! Trouver l'adresse la plus proche
                  console.log('✅ Point valide, recherche de l\'adresse...');
                  
                  // Placer un marqueur temporaire
                  if (meetingMarker) {
                    meetingMarker.remove();
                  }
                  
                  meetingMarker = new maplibregl.Marker({ color: this.detourColor, scale: 1.2 })
                    .setLngLat(clickedPoint)
                    .setPopup(new maplibregl.Popup().setHTML('<strong>📍 Recherche de l\'adresse...</strong>'))
                    .addTo(routeMap);
                  
                  meetingMarker.togglePopup();
                  
                  // Reverse geocoding pour obtenir l'adresse exacte via notre backend
                  const coordsAddress = `Lat: ${clickedPoint[1].toFixed(5)}, Lon: ${clickedPoint[0].toFixed(5)}`;
                  
                  try {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 secondes max
                    
                    // Utiliser notre proxy backend pour éviter CORS
                    const geocodeUrl = `/api/geocode/reverse?lat=${clickedPoint[1]}&lon=${clickedPoint[0]}`;
                    const geocodeResp = await fetch(geocodeUrl, {
                      signal: controller.signal
                    });
                    
                    clearTimeout(timeoutId);
                    
                    if (geocodeResp.ok) {
                      const geocodeData = await geocodeResp.json();
                      console.log('Geocode result:', geocodeData);
                      
                      // Construire une adresse lisible depuis le résultat du géocodage
                      let finalAddress = coordsAddress;
                      if (geocodeData.display_name) {
                        // Utiliser display_name qui contient l'adresse complète
                        finalAddress = geocodeData.display_name;
                      } else if (geocodeData.address) {
                        // Sinon construire depuis les composants
                        const addr = geocodeData.address;
                        const parts = [];
                        if (addr.road) parts.push(addr.road);
                        if (addr.village || addr.town || addr.city) parts.push(addr.village || addr.town || addr.city);
                        if (addr.postcode) parts.push(addr.postcode);
                        finalAddress = parts.join(', ') || coordsAddress;
                      }
                      
                      let finalCoords = clickedPoint;
                      
                      // Utiliser les coordonnées exactes de l'adresse trouvée si disponibles
                      if (geocodeData.lat && geocodeData.lon) {
                        finalCoords = [parseFloat(geocodeData.lon), parseFloat(geocodeData.lat)];
                      }
                      
                      console.log('Final address:', finalAddress);
                      console.log('Final coords:', finalCoords);
                      
                      // Mettre à jour le marqueur avec l'adresse réelle
                      meetingMarker.setLngLat(finalCoords);
                      meetingMarker.setPopup(
                        new maplibregl.Popup().setHTML(
                          `<strong>📍 Point de rencontre</strong><br>${finalAddress}<br><small>Calcul du détour...</small>`
                        )
                      );
                      meetingMarker.togglePopup();
                      
                      // Recalculer le détour avec les coordonnées précises
                      await self.recalculateDetourWithPoint(offer, finalCoords, routeMap, meetingMarker, finalAddress, tripType);
                    } else {
                      // Geocoding échoué, utiliser les coordonnées
                      console.warn('Geocoding failed, using coordinates');
                      meetingMarker.setPopup(
                        new maplibregl.Popup().setHTML(
                          `<strong>📍 Point de rencontre</strong><br>${coordsAddress}<br><small>Calcul du détour...</small>`
                        )
                      );
                      meetingMarker.togglePopup();
                      await self.recalculateDetourWithPoint(offer, clickedPoint, routeMap, meetingMarker, coordsAddress, tripType);
                    }
                  } catch(e) {
                    // CORS ou timeout - utiliser directement les coordonnées
                    console.warn('Geocoding error (CORS/timeout):', e.name);
                    meetingMarker.setPopup(
                      new maplibregl.Popup().setHTML(
                        `<strong>📍 Point de rencontre</strong><br>${coordsAddress}<br><small>Calcul du détour...</small>`
                      )
                    );
                    meetingMarker.togglePopup();
                    await self.recalculateDetourWithPoint(offer, clickedPoint, routeMap, meetingMarker, coordsAddress, tripType);
                  }
                };
                
                routeMap.on('click', onMapClick);
                
                // Nettoyer l'event listener quand on ferme la modal
                const originalClose = this.closeRouteModal.bind(this);
                this.closeRouteModal = () => {
                  routeMap.off('click', onMapClick);
                  this.closeRouteModal = originalClose;
                  originalClose();
                };
              }
            } catch(e) {
              console.warn('Error setting up meeting point selection:', e);
            }
          } else {
            console.log('Missing search center or radius');
          }
        
        // Fit map to zone bounds
        // Si on a une zone cliquable (intersection), zoomer dessus
        // Sinon zoomer sur toute la route
        if (needsMeetingPointSelection && clickableZone && clickableZone.coordinates && clickableZone.coordinates[0]) {
          // Zoomer sur la zone verte d'intersection
          const zoneCoords = clickableZone.coordinates[0];
          const b = new maplibregl.LngLatBounds(zoneCoords[0], zoneCoords[0]);
          for (let i = 1; i < zoneCoords.length; i++) {
            b.extend(zoneCoords[i]);
          }
          routeMap.fitBounds(b, { padding: 80 });
          console.log('📍 Zooming to clickable zone (intersection)');
        } else {
          // Zoomer sur toute la route
          const coords = geo.geometry.coordinates;
          if (Array.isArray(coords) && coords.length) {
            const b = new maplibregl.LngLatBounds(coords[0], coords[0]);
            for (let i = 1; i < coords.length; i++) b.extend(coords[i]);
            if (needsMeetingPointSelection && this.searchCenterCoords) {
              b.extend(this.searchCenterCoords);
            }
            routeMap.fitBounds(b, { padding: 50 });
          }
        }
      } catch(err) {
        console.error('Erreur lors du chargement de la route:', err);
      }
    });
  }
  
  async showDepartureMapModal(offer, tripType) {
    console.log('📍 Showing departure map for offer:', offer.id, 'tripType:', tripType);
    
    // Fermer toute modal existante
    this.closeRouteModal();
    
    // Récupérer les détails de l'offre
    const detailResponse = await fetch(`/api/carpool/${offer.id}`);
    if (!detailResponse.ok) {
      console.error('Failed to load offer details');
      return;
    }
    const detail = await detailResponse.json();
    
    // Déterminer le point de départ selon le tripType
    const isOutbound = tripType === 'outbound';
    const from = isOutbound ? detail.details.fromCoords : detail.details.toCoords;
    const to = isOutbound ? detail.details.toCoords : detail.details.fromCoords;
    // Utiliser current_route_geometry (avec détours) pour l'aller, route_return pour le retour
    const routeGeom = isOutbound ? (detail.current_route_geometry ? {geometry: detail.current_route_geometry} : detail.route_outbound) : detail.route_return;
    
    if (!from || !to || !routeGeom) {
      console.error('Missing coordinates or route geometry');
      return;
    }
    
    const cardColor = isOutbound ? this.colorOutbound : this.colorReturn;
    
    // Créer la modal
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal route-modal" role="dialog" aria-modal="true" style="max-width:90vw;width:800px;height:85vh;display:flex;flex-direction:column;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h3 style="margin:0;font-size:18px;font-weight:700;color:#334155;font-family:${this.fontFamily};">📍 Point de départ</h3>
          <button type="button" class="close-route" aria-label="Fermer" style="background:none;border:none;font-size:24px;cursor:pointer;color:#666;line-height:1;padding:0;width:32px;height:32px;font-family:${this.fontFamily};">×</button>
        </div>
        <div id="route-map-container" style="flex:1;border-radius:12px;overflow:hidden;"></div>
      </div>
    `;
    
    this.shadowRoot.appendChild(backdrop);
    
    // Déterminer le centre : point de rendez-vous si détour, sinon point de départ original
    const detourInfo = offer._detourInfo || offer.details?._detourInfo;
    const centerPoint = (detourInfo && detourInfo.meetingPoint) ? detourInfo.meetingPoint : from;
    
    // Créer la carte
    const mapContainer = backdrop.querySelector('#route-map-container');
    const routeMap = new maplibregl.Map({
      container: mapContainer,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: centerPoint,
      zoom: 14
    });
    
    routeMap.on('load', () => {
      // Ajouter le trajet de base en couleur
      if (routeGeom && routeGeom.type && routeGeom.coordinates) {
        routeMap.addSource('route', {
          type: 'geojson',
          data: { type: 'Feature', geometry: routeGeom }
        });
        
        routeMap.addLayer({
          id: 'route-line',
          type: 'line',
          source: 'route',
          paint: {
            'line-color': cardColor,
            'line-width': 5,
            'line-opacity': 0.9
          }
        });
      }
      
      // Si un détour existe, l'afficher aussi
      const detourInfo = offer._detourInfo || offer.details?._detourInfo;
      if (detourInfo && detourInfo.detourRoute) {
        routeMap.addSource('detour-route', {
          type: 'geojson',
          data: { type: 'Feature', geometry: detourInfo.detourRoute }
        });
        
        routeMap.addLayer({
          id: 'detour-line',
          type: 'line',
          source: 'detour-route',
          paint: {
            'line-color': this.detourColor,
            'line-width': 5,
            'line-opacity': 0.9
          }
        }, 'route-line'); // Placer sous la route originale
        
        // Ajouter un marqueur pour le point de rendez-vous
        if (detourInfo.meetingPoint) {
          new maplibregl.Marker({ color: this.detourColor })
            .setLngLat(detourInfo.meetingPoint)
            .setPopup(new maplibregl.Popup().setHTML(
              `<strong>📍 Point de rendez-vous</strong><br>${detourInfo.meetingAddress || 'Point sélectionné'}`
            ))
            .addTo(routeMap);
        }
      }
      
      // Ajouter le marqueur du point de départ
      new maplibregl.Marker({ color: cardColor })
        .setLngLat(from)
        .addTo(routeMap);
      
      // Zoomer pour tout voir (route + détour si présent)
      if (detourInfo && detourInfo.detourRoute) {
        try {
          const allCoords = [...routeGeom.coordinates, ...detourInfo.detourRoute.coordinates];
          const bounds = new maplibregl.LngLatBounds(allCoords[0], allCoords[0]);
          allCoords.forEach(coord => bounds.extend(coord));
          routeMap.fitBounds(bounds, { padding: 50 });
        } catch (e) {
          // En cas d'erreur, centrer sur le point de rendez-vous
          routeMap.flyTo({ center: detourInfo.meetingPoint, zoom: 14, duration: 1000 });
        }
      } else {
        routeMap.flyTo({ center: from, zoom: 14, duration: 1000 });
      }
    });
    
    // Handlers pour fermer la modal
    const onKey = (e) => { if (e.key === 'Escape') { this.closeRouteModal(); } };
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) this.closeRouteModal(); });
    backdrop.querySelector('button.close-route').addEventListener('click', () => this.closeRouteModal());
    document.addEventListener('keydown', onKey);
    
    // Stocker les références
    this._routeModal = { backdrop, map: routeMap };
    
    // Cleanup
    backdrop.addEventListener('remove', () => {
      document.removeEventListener('keydown', onKey);
      if (routeMap) routeMap.remove();
    }, { once: true });
  }

  async showArrivalMapModal(offer, tripType) {
    console.log('📍 Showing arrival map for offer:', offer.id, 'tripType:', tripType);
    
    // Fermer toute modal existante
    this.closeRouteModal();
    
    // Récupérer les détails de l'offre
    const detailResponse = await fetch(`/api/carpool/${offer.id}`);
    if (!detailResponse.ok) {
      console.error('Failed to load offer details');
      return;
    }
    const detail = await detailResponse.json();
    
    // Déterminer le point d'arrivée selon le tripType
    const isOutbound = tripType === 'outbound';
    const from = isOutbound ? detail.details.fromCoords : detail.details.toCoords;
    const to = isOutbound ? detail.details.toCoords : detail.details.fromCoords;
    // Utiliser current_route_geometry (avec détours) pour l'aller, route_return pour le retour
    const routeGeom = isOutbound ? (detail.current_route_geometry ? {geometry: detail.current_route_geometry} : detail.route_outbound) : detail.route_return;
    
    if (!from || !to || !routeGeom) {
      console.error('Missing coordinates or route geometry');
      return;
    }
    
    const cardColor = isOutbound ? this.colorOutbound : this.colorReturn;
    
    // Créer la modal
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal route-modal" role="dialog" aria-modal="true" style="max-width:90vw;width:800px;height:85vh;display:flex;flex-direction:column;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h3 style="margin:0;font-size:18px;font-weight:700;color:#334155;font-family:${this.fontFamily};">📍 Point d'arrivée</h3>
          <button type="button" class="close-route" aria-label="Fermer" style="background:none;border:none;font-size:24px;cursor:pointer;color:#666;line-height:1;padding:0;width:32px;height:32px;font-family:${this.fontFamily};">×</button>
        </div>
        <div id="route-map-container" style="flex:1;border-radius:12px;overflow:hidden;"></div>
      </div>
    `;
    
    this.shadowRoot.appendChild(backdrop);
    
    // Créer la carte
    const mapContainer = backdrop.querySelector('#route-map-container');
    const routeMap = new maplibregl.Map({
      container: mapContainer,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: to,
      zoom: 14
    });
    
    routeMap.on('load', () => {
      // Ajouter le trajet de base en couleur
      if (routeGeom && routeGeom.type && routeGeom.coordinates) {
        const baseColor = (cardColor || '#7c3aed').substring(0, 7); // Enlever alpha si présent
        routeMap.addSource('route', {
          type: 'geojson',
          data: { type: 'Feature', geometry: routeGeom }
        });
        
        routeMap.addLayer({
          id: 'route-line',
          type: 'line',
          source: 'route',
          paint: {
            'line-color': baseColor,
            'line-width': 5,
            'line-opacity': 0.9
          }
        });
      }
      
      // Si un détour existe, l'afficher aussi
      const detourInfo = offer._detourInfo || offer.details?._detourInfo;
      if (detourInfo && detourInfo.detourRoute) {
        const detourColorClean = (this.detourColor || '#fbbf24').substring(0, 7);
        routeMap.addSource('detour-route', {
          type: 'geojson',
          data: { type: 'Feature', geometry: detourInfo.detourRoute }
        });
        
        routeMap.addLayer({
          id: 'detour-line',
          type: 'line',
          source: 'detour-route',
          paint: {
            'line-color': detourColorClean,
            'line-width': 5,
            'line-opacity': 0.9
          }
        }, 'route-line'); // Placer sous la route originale
        
        // Ajouter un marqueur pour le point de rendez-vous
        if (detourInfo.meetingPoint && Array.isArray(detourInfo.meetingPoint) && detourInfo.meetingPoint.length === 2) {
          new maplibregl.Marker({ color: detourColorClean })
            .setLngLat(detourInfo.meetingPoint)
            .setPopup(new maplibregl.Popup().setHTML(
              `<strong>📍 Point de rendez-vous</strong><br>${detourInfo.meetingAddress || 'Point sélectionné'}`
            ))
            .addTo(routeMap);
        }
      }
      
      // Ajouter le marqueur du point d'arrivée
      new maplibregl.Marker({ color: '#10b981' })
        .setLngLat(to)
        .addTo(routeMap);
      
      // Zoomer pour tout voir (route + détour si présent)
      if (detourInfo && detourInfo.detourRoute) {
        try {
          const allCoords = [...routeGeom.coordinates, ...detourInfo.detourRoute.coordinates];
          const bounds = new maplibregl.LngLatBounds(allCoords[0], allCoords[0]);
          allCoords.forEach(coord => bounds.extend(coord));
          routeMap.fitBounds(bounds, { padding: 50 });
        } catch (e) {
          routeMap.flyTo({ center: to, zoom: 14, duration: 1000 });
        }
      } else {
        routeMap.flyTo({ center: to, zoom: 14, duration: 1000 });
      }
    });
    
    // Handlers pour fermer la modal
    const onKey = (e) => { if (e.key === 'Escape') { this.closeRouteModal(); } };
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) this.closeRouteModal(); });
    backdrop.querySelector('button.close-route').addEventListener('click', () => this.closeRouteModal());
    document.addEventListener('keydown', onKey);
    
    // Stocker les références
    this._routeModal = { backdrop, map: routeMap };
    
    // Cleanup
    backdrop.addEventListener('remove', () => {
      document.removeEventListener('keydown', onKey);
      if (routeMap) routeMap.remove();
    }, { once: true });
  }

  async showMeetingPointMapModal(offer, tripType) {
    console.log('📍 Showing meeting point map for offer:', offer.id, 'tripType:', tripType);
    
    // Fermer toute modal existante
    this.closeRouteModal();
    
    // Utiliser directement offer.details au lieu de re-fetcher depuis l'API
    // car les coordonnées du point de rendez-vous sont stockées localement après sélection
    const detourInfo = offer.details?._detourInfo;
    if (!detourInfo || !detourInfo.meetingPoint || !detourInfo.meetingPoint.coords) {
      console.error('No meeting point coordinates found in offer.details._detourInfo');
      console.log('detourInfo:', detourInfo);
      this.showToast('❌ Point de rendez-vous non disponible', 'error');
      return;
    }
    
    const meetingPointCoords = detourInfo.meetingPoint.coords;
    const meetingPointAddress = detourInfo.meetingPoint.address || 'Point de rendez-vous';
    
    // Récupérer les détails complets de l'offre pour avoir la géométrie de la route
    const detailResponse = await fetch(`/api/carpool/${offer.id}`);
    if (!detailResponse.ok) {
      console.error('Failed to load offer details');
      return;
    }
    const detail = await detailResponse.json();
    
    // Déterminer le trajet selon le tripType
    const isOutbound = tripType === 'outbound';
    // Utiliser current_route_geometry (avec détours) pour l'aller, route_return pour le retour
    const routeGeom = isOutbound ? (detail.current_route_geometry ? {geometry: detail.current_route_geometry} : detail.route_outbound) : detail.route_return;
    const cardColor = isOutbound ? this.colorOutbound : this.colorReturn;
    
    if (!routeGeom) {
      console.error('Missing route geometry');
      return;
    }
    
    // Créer la modal
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal route-modal" role="dialog" aria-modal="true" style="max-width:90vw;width:800px;height:85vh;display:flex;flex-direction:column;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h3 style="margin:0;font-size:18px;font-weight:700;color:#334155;font-family:${this.fontFamily};">📍 Point de rendez-vous</h3>
          <button type="button" class="close-route" aria-label="Fermer" style="background:none;border:none;font-size:24px;cursor:pointer;color:#666;line-height:1;padding:0;width:32px;height:32px;font-family:${this.fontFamily};">×</button>
        </div>
        <div id="route-map-container" style="flex:1;border-radius:12px;overflow:hidden;"></div>
      </div>
    `;
    
    this.shadowRoot.appendChild(backdrop);
    
    // Créer la carte
    const mapContainer = backdrop.querySelector('#route-map-container');
    const routeMap = new maplibregl.Map({
      container: mapContainer,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: meetingPointCoords,
      zoom: 14
    });
    
    routeMap.on('load', () => {
      // Ajouter le trajet de base en couleur
      if (routeGeom && routeGeom.type && routeGeom.coordinates) {
        const baseColor = (cardColor || '#7c3aed').substring(0, 7); // Enlever alpha si présent
        routeMap.addSource('route', {
          type: 'geojson',
          data: { type: 'Feature', geometry: routeGeom }
        });
        
        routeMap.addLayer({
          id: 'route-line',
          type: 'line',
          source: 'route',
          paint: {
            'line-color': baseColor,
            'line-width': 5,
            'line-opacity': 0.9
          }
        });
      }
      
      // Si un détour existe, l'afficher
      if (detourInfo.detourRoute) {
        const detourColorClean = (this.detourColor || '#fbbf24').substring(0, 7);
        routeMap.addSource('detour-route', {
          type: 'geojson',
          data: { type: 'Feature', geometry: detourInfo.detourRoute }
        });
        
        routeMap.addLayer({
          id: 'detour-line',
          type: 'line',
          source: 'detour-route',
          paint: {
            'line-color': detourColorClean,
            'line-width': 5,
            'line-opacity': 0.9
          }
        }, 'route-line'); // Placer sous la route originale
      }
      
      // Ajouter le marqueur du point de rendez-vous avec couleur détour
      const detourColorClean = (this.detourColor || '#fbbf24').substring(0, 7);
      new maplibregl.Marker({ color: detourColorClean })
        .setLngLat(meetingPointCoords)
        .setPopup(
          new maplibregl.Popup().setHTML(`<strong>📍 Point de rendez-vous</strong><br>${meetingPointAddress}`)
        )
        .addTo(routeMap)
        .togglePopup();
      
      // Zoomer pour tout voir (route + détour si présent)
      if (detourInfo.detourRoute) {
        try {
          const allCoords = [...routeGeom.coordinates, ...detourInfo.detourRoute.coordinates];
          const bounds = new maplibregl.LngLatBounds(allCoords[0], allCoords[0]);
          allCoords.forEach(coord => bounds.extend(coord));
          routeMap.fitBounds(bounds, { padding: 50 });
        } catch (e) {
          routeMap.flyTo({ center: meetingPointCoords, zoom: 15, duration: 1000 });
        }
      } else {
        routeMap.flyTo({ center: meetingPointCoords, zoom: 15, duration: 1000 });
      }
    });
    
    // Handlers pour fermer la modal
    const onKey = (e) => { if (e.key === 'Escape') { this.closeRouteModal(); } };
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) this.closeRouteModal(); });
    backdrop.querySelector('button.close-route').addEventListener('click', () => this.closeRouteModal());
    document.addEventListener('keydown', onKey);
    
    // Stocker les références
    this._routeModal = { backdrop, map: routeMap };
    
    // Cleanup
    backdrop.addEventListener('remove', () => {
      document.removeEventListener('keydown', onKey);
      if (routeMap) routeMap.remove();
    }, { once: true });
  }

  closeRouteModal() {
    if (this._routeModal) {
      if (this._routeModal.map) this._routeModal.map.remove();
      if (this._routeModal.backdrop) this._routeModal.backdrop.remove();
      this._routeModal = null;
    }
  }
  
  async recalculateDetourWithPoint(offer, meetingPoint, routeMap, meetingMarker, providedAddress = null, tripType = 'outbound') {
    console.log('🔄 Recalculating detour with user-selected point:', meetingPoint, 'tripType:', tripType);
    
    try {
      // Obtenir les coordonnées de départ et d'arrivée du trajet
      const detailResponse = await fetch(`/api/carpool/${offer.id}`);
      if (!detailResponse.ok) {
        this.showToast('❌ Erreur lors du chargement du trajet', 'error');
        return;
      }
      
      const detail = await detailResponse.json();
      
      // Utiliser la bonne route selon le trip_type
      let routeGeometry;
      let originalRouteDuration;
      
      if (tripType === 'return') {
        // Pour le retour, utiliser route_return
        routeGeometry = detail.route_return?.geometry || detail.route_return;
        originalRouteDuration = detail.route_return?.duration;
        console.log('🔄 Using RETURN route');
      } else {
        // Pour l'aller, utiliser current_route_geometry ou route_outbound
        routeGeometry = detail.current_route_geometry || detail.route_outbound?.geometry;
        originalRouteDuration = detail.route_outbound?.duration;
        console.log('🔄 Using OUTBOUND route');
      }
      
      // Si pas de géométrie stockée, calculer la route à la volée
      if (!routeGeometry) {
        console.log('⚠️ No stored geometry for recalculation, calculating on the fly...');
        
        const departureCoords = detail.departure_coords ? JSON.parse(detail.departure_coords) : null;
        const destinationCoords = detail.destination_coords ? JSON.parse(detail.destination_coords) : null;
        
        if (!departureCoords || !destinationCoords) {
          console.error('❌ No departure/destination coordinates');
          this.showToast('❌ Coordonnées manquantes', 'error');
          return;
        }
        
        // Convertir {lat, lon} en [lon, lat]
        const departureLonLat = [departureCoords.lon, departureCoords.lat];
        const destinationLonLat = [destinationCoords.lon, destinationCoords.lat];
        
        // Pour le retour, inverser départ et destination
        const fromLonLat = tripType === 'return' ? destinationLonLat : departureLonLat;
        const toLonLat = tripType === 'return' ? departureLonLat : destinationLonLat;
        
        const routeResult = await this.fetchRoute([fromLonLat, toLonLat], { overview: 'full' });
        
        if (!routeResult.success || !routeResult.data?.routes?.[0]?.geometry) {
          this.showToast('❌ Impossible de calculer le trajet', 'error');
          return;
        }
        
        routeGeometry = routeResult.data.routes[0].geometry;
        originalRouteDuration = routeResult.data.routes[0].duration;
        console.log('✅ Route calculated for recalculation');
      }
      
      if (!routeGeometry) {
        this.showToast('❌ Trajet non disponible', 'error');
        return;
      }
      
      // Normaliser le format de la géométrie
      if (routeGeometry.geometry && routeGeometry.geometry.coordinates) {
        routeGeometry = routeGeometry.geometry;
      }
      if (!routeGeometry.coordinates) {
        console.error('❌ Format de géométrie invalide:', routeGeometry);
        this.showToast('❌ Format de trajet invalide', 'error');
        return;
      }
      
      let coords = routeGeometry.coordinates;
      
      // IMPORTANT: Pour le retour, INVERSER les coordonnées pour avoir le bon sens
      if (tripType === 'return') {
        coords = [...coords].reverse();
        console.log('🔄 Route coordinates REVERSED for return trip');
      }
      const from = coords[0];
      const to = coords[coords.length - 1];
      
      // Récupérer les points de RDV des passagers déjà confirmés
      // pour les inclure dans le calcul du nouveau détour
      // IMPORTANT: Garder le mapping passager_user_id → coordonnées
      let meetingPoints = [];
      let passengerMapping = [];  // [{coords: [lon, lat], passenger_user_id: xxx}]
      
      // Ajouter les points de RDV des réservations confirmées POUR CE TRIP_TYPE
      if (detail.reservations && detail.reservations.length > 0) {
        const confirmedReservations = detail.reservations.filter(r => r.status === 'confirmed' && r.trip_type === tripType);
        console.log(`📍 ${confirmedReservations.length} passager(s) déjà confirmé(s) pour ${tripType}`);
        
        for (const res of confirmedReservations) {
          if (res.meeting_point_coords) {
            try {
              const pointCoords = typeof res.meeting_point_coords === 'string' 
                ? JSON.parse(res.meeting_point_coords) 
                : res.meeting_point_coords;
              meetingPoints.push(pointCoords);
              // Stocker pickup_order et pickup_time_outbound pour trier chronologiquement
              passengerMapping.push({ 
                coords: pointCoords, 
                passenger_user_id: res.passenger_user_id,
                pickup_order: res.pickup_order || 0,
                pickup_time: res.pickup_time_outbound || res.pickup_time || null
              });
              console.log(`  ✅ Point RDV passager ${res.passenger_user_id}: ${pointCoords} (ordre: ${res.pickup_order})`);
            } catch (e) {
              console.warn('Invalid meeting_point_coords:', res.meeting_point_coords);
            }
          }
        }
      }
      
      // IMPORTANT : Calculer la durée de la route ACTUELLE (avec détours existants) via OSRM
      // pour avoir une base de comparaison fiable avec le trajet AVEC le nouveau détour
      console.log('🔄 Calcul de la durée de la route ACTUELLE (avec détours existants) via OSRM...');
      let realOriginalDuration = null;
      let originalDistance = null;
      
      // Construire les waypoints de la route actuelle : départ + passagers existants + arrivée
      const currentWaypoints = [from, ...meetingPoints, to];
      console.log(`🛣️ Route actuelle avec ${meetingPoints.length} passager(s) déjà confirmé(s)`);
      
      const originalRouteResult = await this.fetchRoute(currentWaypoints, { overview: 'false' });
      if (originalRouteResult.success && originalRouteResult.data.routes?.[0]) {
        realOriginalDuration = originalRouteResult.data.routes[0].duration / 60; // en minutes
        originalDistance = originalRouteResult.data.routes[0].distance / 1000; // en km
        console.log(`✅ Durée route actuelle (OSRM): ${realOriginalDuration.toFixed(1)} min (${originalDistance.toFixed(1)} km)`);
      } else {
        console.warn('⚠️ Impossible de calculer la durée actuelle, utilisation de l\'estimation');
        // Fallback sur l'estimation si OSRM échoue
        realOriginalDuration = originalRouteDuration ? originalRouteDuration / 60 : this.calculateRouteDuration(coords) / 60;
        originalDistance = this.calculateRouteDistance(coords);
      }
      
      // Ajouter le nouveau point de RDV
      // Note: passenger_user_id sera null pour les nouveaux passagers en cours de sélection
      // Il sera rempli côté backend lors de la confirmation
      const userId = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
      meetingPoints.push(meetingPoint);
      // Pour le nouveau passager, calculer un pickup_order approximatif basé sur la position géométrique
      const newPassengerRouteIndex = this.findNearestPointOnRoute(meetingPoint, coords);
      passengerMapping.push({ 
        coords: meetingPoint, 
        passenger_user_id: userId,
        pickup_order: newPassengerRouteIndex,
        pickup_time: null // Sera calculé par le backend
      });
      
      // IMPORTANT: Trier les points de RDV par pickup_order chronologique
      // Les passagers existants ont pickup_order de la BDD, le nouveau a l'index géométrique
      if (meetingPoints.length > 1) {
        // Trier par pickup_order (ordre chronologique)
        const indexedPoints = passengerMapping.map((p, idx) => ({
          ...p,
          point: meetingPoints[idx],
          sortKey: p.pickup_order || 0
        }));
        
        indexedPoints.sort((a, b) => a.sortKey - b.sortKey);
        
        // Reconstruire les tableaux triés
        meetingPoints = indexedPoints.map(item => item.point);
        passengerMapping = indexedPoints.map(item => ({ 
          coords: item.coords, 
          passenger_user_id: item.passenger_user_id,
          pickup_order: item.pickup_order,
          pickup_time: item.pickup_time
        }));
        
        console.log(`🔄 Points triés par ordre chronologique (pickup_order)`);
        console.log('📋 Ordre des passagers après tri:', passengerMapping.map(p => `${p.passenger_user_id || 'nouveau'} (ordre: ${p.pickup_order})`));
      }
      
      // Construire le tableau de waypoints: départ + points triés + arrivée
      const waypoints = [from, ...meetingPoints, to];
      
      // Extraire juste les IDs dans l'ordre géographique (pour envoyer au backend)
      const waypointPassengerIds = passengerMapping.map(p => p.passenger_user_id);
      
      console.log(`🛣️ Calcul du détour avec ${waypoints.length} points (départ + ${meetingPoints.length} passagers + arrivée)`);
      console.log(`⚠️ Note: Le moteur peut recalculer un chemin optimal différent de la route originale`);
      
      // Afficher la route ORIGINALE du conducteur en gris sur la carte
      // pour que l'utilisateur voie la différence
      if (routeMap && routeMap.getSource('original-route')) {
        routeMap.removeLayer('original-route-layer');
        routeMap.removeSource('original-route');
      }
      if (routeMap) {
        routeMap.addSource('original-route', {
          type: 'geojson',
          data: {
            type: 'Feature',
            geometry: routeGeometry
          }
        });
        routeMap.addLayer({
          id: 'original-route-layer',
          type: 'line',
          source: 'original-route',
          paint: {
            'line-color': '#94a3b8', // Gris pour la route originale
            'line-width': 3,
            'line-opacity': 0.5,
            'line-dasharray': [2, 2] // Pointillés
          }
        });
        console.log('📍 Route originale affichée en gris pointillé');
      }
      
      // Appeler l'API de routing pour calculer le détour avec TOUS les points
      const routeResult = await this.fetchRoute(waypoints, { overview: 'full' });
      
      if (!routeResult.success) {
        this.showToast('❌ Services de routing indisponibles', 'error');
        return;
      }
      
      const osrmData = routeResult.data;
      const routingEngine = osrmData.routes?.[0]?.routing_engine || 'unknown';
      console.log(`✅ Route calculée via ${routeResult.source} (moteur: ${routingEngine})`);
      
      if (osrmData.code !== 'Ok' || !osrmData.routes || !osrmData.routes[0]) {
        this.showToast('❌ Aucun trajet trouvé', 'error');
        return;
      }
      
      const detourRoute = osrmData.routes[0];
      const detourDistance = detourRoute.distance / 1000; // en km
      const detourDuration = detourRoute.duration / 60; // en minutes (utiliser OSRM tel quel)
      
      console.log(`⏱️ Durée OSRM avec détour: ${detourDuration.toFixed(1)}min (${detourDistance.toFixed(1)}km)`);
      
      // Comparer les routes
      const detourGeometry = detourRoute.geometry;
      const detourCoords = detourGeometry.coordinates;
      const originalCoords = routeGeometry.coordinates;
      
      // Calculer la divergence entre les routes
      let maxDivergence = 0;
      for (let i = 0; i < Math.min(detourCoords.length, originalCoords.length); i++) {
        const dist = this.calculateDistance(
          detourCoords[i][1], detourCoords[i][0],
          originalCoords[i][1], originalCoords[i][0]
        );
        if (dist > maxDivergence) maxDivergence = dist;
      }
      
      if (maxDivergence > 0.5) { // Plus de 500m de divergence
        console.warn(`⚠️ Route recalculée diverge de ${maxDivergence.toFixed(1)}km de la route originale`);
      }
      
      // Distance et durée originales : déjà calculées avec OSRM ci-dessus
      // originalDistance et realOriginalDuration incluent déjà les détours existants
      
      const originalDuration = realOriginalDuration || this.calculateRouteDuration(coords) / 60;
      
      // Si originalDistance n'a pas été calculée (fallback), l'estimer
      if (!originalDistance) {
        originalDistance = this.calculateRouteDistance(coords);
      }
      
      console.log(`⏱️ Durée originale OSRM: ${originalDuration.toFixed(1)}min (${originalDistance.toFixed(1)}km)`);
      
      let additionalDistance = detourDistance - originalDistance;
      let additionalTime = detourDuration - originalDuration;
      
      console.log(`📊 Comparaison OSRM réelle:
        - Direct: ${originalDistance.toFixed(2)}km en ${originalDuration.toFixed(1)}min
        - Avec détour: ${detourDistance.toFixed(2)}km en ${detourDuration.toFixed(1)}min
        - Différence: +${additionalDistance.toFixed(2)}km / +${additionalTime.toFixed(1)}min`);
      
      // Si le détour est plus rapide que l'original (OSRM a trouvé un meilleur chemin),
      // on considère que c'est un détour minimal de 1 minute
      if (additionalTime < 0) {
        console.warn('⚠️ Le détour est plus rapide que le trajet direct (OSRM a optimisé), fixé à +1 min minimum');
        additionalTime = 1;
      }
      if (additionalDistance < 0) {
        console.warn('⚠️ Le détour est plus court que le trajet direct (OSRM a optimisé), fixé à +0.1 km minimum');
        additionalDistance = 0.1;
      }
      
      // Récupérer le bandeau de status
      const statusBanner = this._routeModal.backdrop.querySelector('#detour-status-banner');
      const statusContent = this._routeModal.backdrop.querySelector('#detour-status-content');
      
      // Vérifier le budget temps du conducteur
      const detourTimeLeft = this._currentOfferDetourTimeLeft || 60;
      if (additionalTime > detourTimeLeft) {
        // Afficher le refus dans le bandeau
        if (statusBanner && statusContent) {
          statusContent.innerHTML = `
            <div style="display:flex;align-items:center;gap:12px;">
              <div style="font-size:32px;font-family:${this.fontFamily};">⏱️</div>
              <div style="flex:1;">
                <div style="font-weight:700;font-size:16px;color:#dc2626;margin-bottom:4px;font-family:${this.fontFamily};">❌ Détour impossible</div>
                <div style="font-size:14px;color:#666;font-family:${this.fontFamily};">
                  Ce point nécessite <strong style="color:#dc2626;">+${additionalTime.toFixed(0)} minutes</strong> de détour<br>
                  <small>Budget disponible du conducteur : ${detourTimeLeft} min</small>
                </div>
              </div>
            </div>
          `;
          statusBanner.style.display = 'block';
          statusBanner.style.borderTopColor = '#dc2626';
        }
        
        meetingMarker.setPopup(
          new maplibregl.Popup().setHTML(
            `<strong style="color:#dc2626;">⏱️ Détour impossible</strong><br>
            Ce point nécessite +${additionalTime.toFixed(0)} min<br>
            <small>Budget conducteur : ${detourTimeLeft} min</small>`
          )
        );
        meetingMarker.togglePopup();
        return;
      }
      
      // Utiliser l'adresse fournie ou faire un reverse geocode via notre backend
      let meetingAddress = providedAddress;
      if (!meetingAddress) {
        try {
          const geocodeUrl = `/api/geocode/reverse?lat=${meetingPoint[1]}&lon=${meetingPoint[0]}`;
          const geocodeResp = await fetch(geocodeUrl, { timeout: 5000 });
          if (geocodeResp.ok) {
            const geocodeData = await geocodeResp.json();
            meetingAddress = geocodeData.address;
          }
        } catch(e) {
          console.warn('Geocoding failed:', e);
        }
      }
      
      if (!meetingAddress) {
        meetingAddress = `Lat: ${meetingPoint[1].toFixed(5)}, Lon: ${meetingPoint[0].toFixed(5)}`;
      }
      
      // Calculer la distance passager (meeting point → destination) pour le prix
      const destinationCoords = coords[coords.length - 1];
      let passengerDistanceKm = 0;
      
      // Essayer de calculer avec OSRM pour avoir la distance réelle sur routes
      try {
        const passengerRouteResult = await this.fetchRoute([meetingPoint, destinationCoords], { overview: 'false' });
        if (passengerRouteResult.success && passengerRouteResult.data.routes?.[0]) {
          passengerDistanceKm = passengerRouteResult.data.routes[0].distance / 1000;
          console.log(`📏 Distance passager (OSRM): ${passengerDistanceKm.toFixed(1)} km`);
        } else {
          // Fallback : estimation
          passengerDistanceKm = this.haversineMeters(meetingPoint, destinationCoords) * 1.3 / 1000;
          console.log(`📏 Distance passager (estimation): ${passengerDistanceKm.toFixed(1)} km`);
        }
      } catch(e) {
        // Fallback en cas d'erreur
        passengerDistanceKm = this.haversineMeters(meetingPoint, destinationCoords) * 1.3 / 1000;
        console.log(`📏 Distance passager (fallback): ${passengerDistanceKm.toFixed(1)} km`);
      }
      
      // Calculer le prix selon la formule BlaBlaCar (distance passager uniquement)
      // Le passager paie pour SA distance (meeting point → destination)
      const adjustedPrice = this.computeBasePrice(passengerDistanceKm, !!offer.details?.includeTolls);
      
      console.log(`💰 Prix calculé: ${adjustedPrice.toFixed(2)}€ pour ${passengerDistanceKm.toFixed(1)}km de trajet passager`);
      
      // Ajouter l'ordre des passagers dans detourRoute pour que le backend puisse
      // correctement assigner les legs aux passagers
      detourRoute.waypoint_passenger_ids = waypointPassengerIds;
      console.log('📋 Ordre des passagers envoyé au backend:', waypointPassengerIds);
      
      // Mettre à jour l'offre avec les nouvelles infos
      offer._detourInfo = {
        meetingPoint: {
          coords: meetingPoint,
          address: meetingAddress,
          distanceFromSearch: this.haversineMeters(this.searchCenterCoords || meetingPoint, meetingPoint)
        },
        meetingAddress: meetingAddress,
        detourRoute: detourRoute, // Objet complet avec geometry + duration + waypoint_passenger_ids
        additionalDistance: additionalDistance,
        additionalTime: additionalTime, // Temps de détour en minutes
        detourDuration: detourDuration,
        adjustedPrice: adjustedPrice,
        passengerDistance: passengerDistanceKm,
        totalDriverDistance: detourDistance,
        waypointPassengerIds: waypointPassengerIds  // Ordre géographique des passagers
      };
      
      // IMPORTANT: Mettre à jour aussi dans offer.details._detourInfo pour cohérence
      if (offer.details) {
        offer.details._detourInfo = {...offer._detourInfo};
        offer.details._detourCalculated = true;
      }
      
      // Marquer l'offre comme ayant un détour calculé
      offer._detourCalculated = true;
      
      console.log('✅ Detour recalculated:', offer._detourInfo);
      
      // Afficher la validation dans le bandeau
      if (statusBanner && statusContent) {
        const divergenceWarning = maxDivergence > 0.5 ? 
          `<div style="margin-top:8px;padding:8px;background:#fef3c7;border-left:3px solid #f59e0b;font-size:12px;border-radius:4px;">
            ⚠️ Le trajet calculé peut différer légèrement de votre route habituelle (divergence max: ${maxDivergence.toFixed(1)}km)<br>
            <small>Route originale affichée en gris pointillé sur la carte</small>
          </div>` : '';
        
        statusContent.innerHTML = `
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="font-size:32px;font-family:${this.fontFamily};">✅</div>
            <div style="flex:1;">
              <div style="font-weight:700;font-size:16px;color:#059669;margin-bottom:4px;font-family:${this.fontFamily};">📍 Point de rencontre valide</div>
              <div style="font-size:14px;color:#666;font-family:${this.fontFamily};">
                <strong>${meetingAddress}</strong><br>
                Détour : <strong style="color:#059669;">+${additionalDistance.toFixed(1)} km • +${additionalTime.toFixed(0)} min</strong><br>
                <small style="color:#059669;">Budget temps OK (${detourTimeLeft} min disponibles)</small>
                ${divergenceWarning}
              </div>
            </div>
          </div>
        `;
        statusBanner.style.display = 'block';
        statusBanner.style.borderTopColor = '#10b981';
      }
      
      // Mettre à jour le popup du marqueur
      meetingMarker.setPopup(
        new maplibregl.Popup().setHTML(
          `<strong style="color:#10b981;">📍 Point de rencontre valide</strong><br>
          ${meetingAddress}<br>
          <small>+${additionalDistance.toFixed(1)}km • +${additionalTime.toFixed(0)} min</small><br>
          <small style="color:#059669;">✓ Budget temps OK (${detourTimeLeft}min disponibles)</small>`
        )
      );
      
      // Redessiner le trajet avec le détour sur la carte
      // Important : placer le détour SOUS la route originale
      if (routeMap.getSource('detour-route')) {
        routeMap.removeLayer('detour-line');
        routeMap.removeSource('detour-route');
      }
      
      const detourColorClean = (this.detourColor || '#fbbf24').substring(0, 7); // Enlever alpha si présent
      routeMap.addSource('detour-route', {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: detourRoute.geometry
        }
      });
      
      routeMap.addLayer({
        id: 'detour-line',
        type: 'line',
        source: 'detour-route',
        paint: {
          'line-color': detourColorClean,
          'line-width': 6,
          'line-opacity': 0.9
        }
      }, 'route-line'); // Placer AVANT 'route-line' pour être en dessous
      
      // Ne pas ajuster les bounds - garder le zoom actuel sur la zone verte
      // L'utilisateur a déjà la bonne vue centrée sur la zone de sélection
      
      // Afficher le résultat à l'utilisateur
      this.showToast(
        `✅ Point de rencontre validé ! Prix: ${adjustedPrice.toFixed(2)}€ (+${additionalDistance.toFixed(1)}km)`,
        'success'
      );
      
      // Activer le bouton de confirmation
      const confirmBtn = this.shadowRoot.getElementById('confirm-meeting-point-btn');
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.style.cursor = 'pointer';
        confirmBtn.style.background = this.detourColor;
        confirmBtn.style.color = '#fff';
      }
      
      // Mettre à jour l'affichage de la carte des résultats si on y retourne
      // Note: on a déjà mis à jour offer.details._detourInfo.meetingPoint.address ci-dessus
      // donc pas besoin de copier tout l'objet, juste s'assurer que les autres champs sont à jour
      if (offer.details && offer.details._detourInfo) {
        offer.details._detourInfo.adjustedPrice = adjustedPrice;
        offer.details._detourInfo.extraTime = additionalTime;
      }
      
    } catch(err) {
      console.error('Error recalculating detour:', err);
      this.showToast('❌ Erreur lors du calcul du détour', 'error');
    }
  }
  
  // Calcule la distance entre deux points en km
  calculateDistance(lat1, lon1, lat2, lon2) {
    const distanceMeters = this.haversineMeters([lon1, lat1], [lon2, lat2]);
    return distanceMeters / 1000; // Convertir en km
  }

  calculateRouteDistance(coords) {
    let total = 0;
    for (let i = 1; i < coords.length; i++) {
      total += this.haversineMeters(coords[i-1], coords[i]);
    }
    return total / 1000; // Convertir en km
  }
  
  // Estime la durée du trajet en secondes avec vitesses moyennes réalistes
  calculateRouteDuration(coords) {
    const distanceKm = this.calculateRouteDistance(coords);
    
    // Vitesses moyennes réalistes selon la distance (cohérent avec backend)
    let averageSpeedKmh;
    if (distanceKm < 5) {
      averageSpeedKmh = 35; // Urbain court
    } else if (distanceKm < 20) {
      averageSpeedKmh = 55; // Mixte
    } else if (distanceKm < 50) {
      averageSpeedKmh = 70; // Interurbain (ex: Lille-Lens)
    } else {
      averageSpeedKmh = 85; // Longue distance autoroutes
    }
    
    const durationHours = distanceKm / averageSpeedKmh;
    return durationHours * 3600; // Retourner en secondes
  }
  
  async reserveBothTrips(outboundOffer, returnOffer) {
    // Réserver l'aller et le retour avec une seule confirmation
    // ✅ V2: Pas besoin de userId - système basé sur email
    
    // Vérifier qu'il n'y a pas déjà de réservations existantes
    const userId = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
    if (userId && Array.isArray(this.myReservations)) {
      const hasOutbound = this.myReservations.some(res => res && res.trip_type === 'outbound');
      const hasReturn = this.myReservations.some(res => res && res.trip_type === 'return');
      
      if (hasOutbound || hasReturn) {
        const msg = hasOutbound && hasReturn 
          ? "Vous avez déjà des réservations pour l'aller ET le retour."
          : hasOutbound 
            ? "Vous avez déjà une réservation pour l'aller."
            : "Vous avez déjà une réservation pour le retour.";
        alert(`${msg} Annulez-les d'abord pour en créer de nouvelles.`);
        return;
      }
    }
    
    // Afficher la popup de confirmation
    this.closeReservationPopup();
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="res-title">
        <h2 id="res-title">Confirmer la réservation aller-retour</h2>
        <div style="margin-bottom:16px;">
          <p style="margin:8px 0;"><strong>➡️ Aller:</strong> ${(outboundOffer.departure||'').replace(/"/g,'&quot;')} → ${(outboundOffer.destination||'').replace(/"/g,'&quot;')}</p>
          <p style="margin:8px 0;"><strong>⬅️ Retour:</strong> ${(returnOffer.departure||'').replace(/"/g,'&quot;')} → ${(returnOffer.destination||'').replace(/"/g,'&quot;')}</p>
        </div>
        <div class="warning">Merci de n'effectuer une réservation que si vous êtes certain de pouvoir honorer les deux rendez-vous. En cas d'empêchement, prévenez le conducteur au plus tôt.</div>
        <p>Souhaitez-vous vraiment réserver ce covoiturage aller-retour ?</p>
        <div class="buttons">
          <button type="button" class="cancel" aria-label="Annuler">Annuler</button>
          <button type="button" class="confirm" aria-label="Confirmer">Réserver aller-retour</button>
        </div>
      </div>`;
    this.shadowRoot.appendChild(backdrop);
    
    const onKey = (e) => { if (e.key === 'Escape') { this.closeReservationPopup(); } };
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) this.closeReservationPopup(); });
    backdrop.querySelector('button.cancel').addEventListener('click', () => this.closeReservationPopup());
    backdrop.querySelector('button.confirm').addEventListener('click', async () => {
      this.closeReservationPopup();
      
      try {
        // Réserver l'aller
        await this.reserveOffer(outboundOffer, 'outbound');
        
        // Attendre un peu pour que la première réservation soit bien enregistrée
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Réserver le retour
        await this.reserveOffer(returnOffer, 'return');
        
        // Afficher un message de succès
        alert('✅ Réservations aller-retour confirmées !');
        
      } catch(e) {
        console.error('Erreur lors de la réservation aller-retour:', e);
        alert('❌ Erreur lors de la réservation. Veuillez réessayer.');
      }
    });
    
    document.addEventListener('keydown', onKey, { once:true });
    this._reservationBackdrop = backdrop;
  }
  
  showReservationPopup(offer, tripType = 'outbound') {
    // ✅ V2: Pas besoin de userId - réservation par email
    // Vérifier si l'utilisateur a déjà une réservation pour ce type de trajet (peu importe l'offre)
    const userId = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
    if (userId && Array.isArray(this.myReservations)) {
      const existingReservation = this.myReservations.find(res => 
        res && (res.trip_type || 'outbound') === tripType
      );
      if (existingReservation) {
        const tripLabel = tripType === 'outbound' ? "l'aller" : "le retour";
        const route = `${existingReservation.departure} → ${existingReservation.destination}`;
        alert(`Vous avez déjà une réservation pour ${tripLabel} (${route}). Annulez-la d'abord pour en créer une nouvelle.`);
        return;
      }
    }
    
    this.closeReservationPopup();
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="res-title">
        <h2 id="res-title">Confirmer la réservation</h2>
        <p><strong>${(offer.departure||'').replace(/"/g,'&quot;')} → ${(offer.destination||'').replace(/"/g,'&quot;')}</strong></p>
        <div class="warning">Merci de n'effectuer une réservation que si vous êtes certain de pouvoir honorer le rendez-vous. En cas d'empêchement, prévenez le conducteur au plus tôt.</div>
        <p>Souhaitez-vous vraiment réserver ce covoiturage ?</p>
        <div class="buttons">
          <button type="button" class="cancel" aria-label="Annuler la réservation">Annuler</button>
          <button type="button" class="confirm" aria-label="Confirmer la réservation">Réserver</button>
        </div>
      </div>`;
    this.shadowRoot.appendChild(backdrop);
    const onKey = (e) => { if (e.key === 'Escape') { this.closeReservationPopup(); } };
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) this.closeReservationPopup(); });
    backdrop.querySelector('button.cancel').addEventListener('click', () => this.closeReservationPopup());
    backdrop.querySelector('button.confirm').addEventListener('click', () => { this.reserveOffer(offer, tripType); });
    document.addEventListener('keydown', onKey, { once:true });
    this._reservationBackdrop = backdrop;
  }
  closeReservationPopup() {
    if (this._reservationBackdrop) { try { this._reservationBackdrop.remove(); } catch(_){} this._reservationBackdrop = null; }
  }
  
  showPassengerDetailsPopup(offer, tripType) {
    return new Promise((resolve, reject) => {
      this.closeReservationPopup();
      
      const backdrop = document.createElement('div');
      backdrop.className = 'modal-backdrop';
      backdrop.innerHTML = `
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="passenger-details-title" style="max-width: 500px;">
          <h2 id="passenger-details-title" style="margin-bottom: 24px; font-family: ${this.fontFamily};">📋 Vos coordonnées</h2>
          
          <div style="background: #e3f2fd; padding: 16px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #2196F3;">
            <p style="margin: 4px 0; color: #333; font-size: 14px;"><strong>${tripType === 'outbound' ? '➡️' : '⬅️'} ${offer.departure || ''} → ${offer.destination || ''}</strong></p>
            <p style="margin: 4px 0; color: #666; font-size: 13px;">📅 ${this.formatDateFR(offer.datetime)}</p>
          </div>
          
          <form id="passenger-form" style="display: flex; flex-direction: column; gap: 16px;">
            <div>
              <label for="passenger-name" style="display: block; margin-bottom: 6px; font-weight: 600; color: #333; font-family: ${this.fontFamily};">Nom complet *</label>
              <input 
                type="text" 
                id="passenger-name" 
                required 
                placeholder="Ex: Jean Dupont"
                style="width: 100%; padding: 10px 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; font-family: ${this.fontFamily}; box-sizing: border-box;"
              />
            </div>
            
            <div>
              <label for="passenger-email" style="display: block; margin-bottom: 6px; font-weight: 600; color: #333; font-family: ${this.fontFamily};">Email *</label>
              <input 
                type="email" 
                id="passenger-email" 
                required 
                placeholder="Ex: jean.dupont@email.com"
                style="width: 100%; padding: 10px 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; font-family: ${this.fontFamily}; box-sizing: border-box;"
              />
            </div>
            
            <div>
              <label for="passenger-email-confirm" style="display: block; margin-bottom: 6px; font-weight: 600; color: #333; font-family: ${this.fontFamily};">Confirmer l'email *</label>
              <input 
                type="email" 
                id="passenger-email-confirm" 
                required 
                placeholder="Saisissez à nouveau votre email"
                style="width: 100%; padding: 10px 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; font-family: ${this.fontFamily}; box-sizing: border-box;"
              />
              <p style="margin: 6px 0 0 0; font-size: 12px; color: #666; font-family: ${this.fontFamily};">✅ Pour éviter les erreurs de frappe</p>
            </div>
            
            <div>
              <label for="passenger-phone" style="display: block; margin-bottom: 6px; font-weight: 600; color: #333; font-family: ${this.fontFamily};">WhatsApp / Téléphone *</label>
              <input 
                type="tel" 
                id="passenger-phone" 
                required 
                placeholder="Ex: 06 12 34 56 78"
                style="width: 100%; padding: 10px 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; font-family: ${this.fontFamily}; box-sizing: border-box;"
              />
              <p style="margin: 6px 0 0 0; font-size: 12px; color: #666; font-family: ${this.fontFamily};">💬 Pour la mise en relation directe avec le conducteur</p>
            </div>
            
            <div style="background: #e3f2fd; padding: 12px; border-radius: 6px; margin-top: 8px; border-left: 3px solid #2196F3;">
              <p style="margin: 0; font-size: 13px; color: #1565c0; line-height: 1.5; font-family: ${this.fontFamily};">
                🔒 <strong>Caution d'engagement : 1,00 €</strong><br>
                Remboursée si le conducteur refuse.<br>
                Le reste du prix se règle directement avec le conducteur.
              </p>
            </div>
            
            <div class="buttons" style="margin-top: 8px;">
              <button type="button" class="cancel" aria-label="Annuler">Annuler</button>
              <button type="submit" class="confirm" aria-label="Envoyer la demande">✉️ Envoyer ma demande</button>
            </div>
          </form>
        </div>`;
      
      this.shadowRoot.appendChild(backdrop);
      this._reservationBackdrop = backdrop;
      
      const form = backdrop.querySelector('#passenger-form');
      const nameInput = backdrop.querySelector('#passenger-name');
      const emailInput = backdrop.querySelector('#passenger-email');
      const emailConfirmInput = backdrop.querySelector('#passenger-email-confirm');
      const phoneInput = backdrop.querySelector('#passenger-phone');
      
      // Focus sur le premier champ
      setTimeout(() => nameInput.focus(), 100);
      
      // Handler fermeture
      const close = () => {
        this.closeReservationPopup();
        reject(new Error('Cancelled by user'));
      };
      
      // Events
      backdrop.querySelector('.cancel').addEventListener('click', close);
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) close();
      });
      
      const onKey = (e) => {
        if (e.key === 'Escape') close();
      };
      document.addEventListener('keydown', onKey, { once: true });
      
      // Submit handler
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const name = nameInput.value.trim();
        const email = emailInput.value.trim();
        const emailConfirm = emailConfirmInput.value.trim();
        const phone = phoneInput.value.trim();
        
        // Validation
        if (!name) {
          alert('Le nom est requis');
          nameInput.focus();
          return;
        }
        
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email || !emailRegex.test(email)) {
          alert('Un email valide est requis');
          emailInput.focus();
          return;
        }
        
        // Vérifier que les deux emails correspondent
        if (email !== emailConfirm) {
          alert('⚠️ Les deux emails ne correspondent pas.\n\nVeuillez vérifier votre saisie pour éviter les erreurs.');
          emailConfirmInput.focus();
          emailConfirmInput.select();
          return;
        }
        
        if (!phone) {
          alert('Le téléphone est requis pour la mise en relation WhatsApp');
          phoneInput.focus();
          return;
        }
        
        this.closeReservationPopup();
        resolve({ name, email, phone });
      });
    });
  }
  
  async reserveOffer(offer, tripType = 'outbound') {
    try {
      // ✅ V2: Collecter email/téléphone/nom du passager via popup élégante
      let passengerDetails;
      try {
        passengerDetails = await this.showPassengerDetailsPopup(offer, tripType);
      } catch (err) {
        // Utilisateur a annulé
        console.log('Reservation cancelled by user');
        return;
      }
      
      const passengerName = passengerDetails.name;
      const passengerEmail = passengerDetails.email;
      const passengerPhone = passengerDetails.phone;
      
      // Récupérer le nombre de passagers demandé
      const seatsEl = this.shadowRoot.getElementById('seats');
      const requestedSeats = seatsEl ? parseInt(seatsEl.value, 10) : 1;
      
      // Récupérer le temps de détour si l'offre nécessite un détour
      let detourTime = 0;
      let meetingPoint = null;
      let meetingAddress = null;
      let detourRoute = null;
      
      if (offer._detourInfo) {
        if (offer._detourInfo.additionalTime) {
          detourTime = Math.round(offer._detourInfo.additionalTime);
          console.log('Sending detour_time to API:', detourTime, 'minutes');
        }
        if (offer._detourInfo.meetingPoint) {
          meetingPoint = offer._detourInfo.meetingPoint;
          console.log('Sending meeting_point to API:', meetingPoint);
        }
        if (offer._detourInfo.meetingAddress) {
          meetingAddress = offer._detourInfo.meetingAddress;
          console.log('Sending meeting_address to API:', meetingAddress);
        }
        if (offer._detourInfo.detourRoute) {
          detourRoute = offer._detourInfo.detourRoute;
          console.log('Sending detour_route to API:', detourRoute);
        }
      }
      
      // Extraire la date de l'offre (format YYYY-MM-DD)
      let offerDate = null;
      if (offer.datetime) {
        const datetimeStr = offer.datetime;
        // Extraire la partie date (YYYY-MM-DD) de datetime (ex: "2025-01-15T09:00:00")
        offerDate = datetimeStr.split('T')[0];
      }
      
      // ✅ V2: Payload avec email/phone au lieu de user_id + date pour mode ponctuel
      const payload = { 
        offer_id: offer.id, 
        passenger_name: passengerName.trim(),
        passenger_email: passengerEmail.trim(),
        passenger_phone: passengerPhone.trim(),
        date: offerDate,  // Date pour le mode ponctuel (YYYY-MM-DD)
        pickup_coords: meetingPoint,  // [lon, lat]
        pickup_address: meetingAddress,
        passengers: requestedSeats,
        detour_time: detourTime,
        meeting_point: meetingPoint,
        meeting_address: meetingAddress,
        detour_route: detourRoute,
        trip_type: tripType
      };
      
      // 💳 Paiement simulé (1€) avant réservation
      const doReservation = async () => {
        // ✅ V2: Appeler /api/v2/reservations/ponctual pour mode ponctuel
        const res = await fetch('/api/v2/reservations/ponctual', { 
          method:'POST', 
          headers:{'Content-Type':'application/json'}, 
          credentials:'include', 
          body:JSON.stringify(payload) 
        });
        
        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          const errorMsg = errorData.error || 'Réservation échouée';
          throw new Error(errorMsg);
        }
        
        const resData = await res.json();
        
        alert(
          `✅ Demande envoyée à ${offer.driver_name || 'le conducteur'} !\n\n` +
          `Vous recevrez un email dès qu'il aura pris une décision.\n\n` +
          `Un email de confirmation vous a été envoyé.`
        );
        this.closeReservationPopup();
      };
      
      // Vérifier si le simulateur de paiement est disponible
      if (window.CarettePaymentSimulator) {
        const payment = new window.CarettePaymentSimulator();
        payment.show({
          amount: '1,00 €',
          onConfirm: async () => {
            try {
              await doReservation();
            } catch (e) {
              console.error(e);
              alert(e.message || 'Désolé, la réservation n\'a pas pu être effectuée.');
            }
          },
          onCancel: () => {
            console.log('Paiement annulé par l\'utilisateur');
          }
        });
      } else {
        // Pas de payment-simulator chargé, réservation directe
        await doReservation();
      }
      
      // Met à jour localement le compteur de réservation pour éviter un refetch immédiat
      try {
        if (offer) {
          offer.reserved_count = Number(offer.reserved_count || 0) + requestedSeats;
          // Mettre à jour le compteur spécifique selon le type de trajet
          if (tripType === 'outbound') {
            offer.reserved_count_outbound = Number(offer.reserved_count_outbound || 0) + requestedSeats;
          } else if (tripType === 'return') {
            offer.reserved_count_return = Number(offer.reserved_count_return || 0) + requestedSeats;
          }
          // Mettre à jour dans le cache global _offers
          if (Array.isArray(this._offers)) {
            const idx = this._offers.findIndex(o => String(o.id) === String(offer.id));
            if (idx >= 0) {
              this._offers[idx].reserved_count = offer.reserved_count;
              if (tripType === 'outbound') {
                this._offers[idx].reserved_count_outbound = offer.reserved_count_outbound;
              } else if (tripType === 'return') {
                this._offers[idx].reserved_count_return = offer.reserved_count_return;
              }
            }
          }
        }
      } catch(_) {}
      // Re-rendu (garde filtre actif le cas échéant)
      try {
        if (this.searchCenterCoords) this.renderFindOffersFiltered(); else this.renderFindOffers();
      } catch(_) {}
      const card = this.shadowRoot.querySelector(`.offer-card[data-offer-id="${offer.id}"]`);
      if (card) card.classList.add('selected');
    } catch(e) {
      console.error(e);
      const errorMsg = e.message || 'Désolé, la réservation n\'a pas pu être effectuée.';
      alert(errorMsg);
    }
  }

}



customElements.define("carpool-offer-widget", CarpoolOfferWidget);