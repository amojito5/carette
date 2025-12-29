/**
 * Carette - Module de Paiement Simulé
 * Popup 1€ pour intégration dans le widget existant
 */

class CarettePaymentSimulator {
  constructor() {
    this.backdrop = null;
  }

  /**
   * Afficher la popup de paiement simulé
   * @param {Object} options - Options de la popup
   * @param {string} options.amount - Montant (défaut: "1,00 €")
   * @param {Function} options.onConfirm - Callback après paiement
   * @param {Function} options.onCancel - Callback annulation
   */
  show(options = {}) {
    const {
      amount = "1,00 €",
      onConfirm = () => {},
      onCancel = () => {}
    } = options;

    // Créer le backdrop si nécessaire
    this.close();
    
    this.backdrop = document.createElement('div');
    this.backdrop.className = 'carette-payment-backdrop';
    this.backdrop.innerHTML = `
      <div class="carette-payment-modal">
        <span class="carette-payment-close">&times;</span>
        
        <div class="carette-payment-content">
          <h2>💳 Paiement Sécurisé</h2>
          <div class="carette-payment-amount">${amount}</div>
          <p>Frais de réservation</p>
          
          <div class="carette-payment-notice">
            <strong>⚠️ MODE TEST</strong><br>
            En production, ceci sera un vrai paiement Stripe.<br>
            Pour tester, cliquez simplement sur "Payer".
          </div>
          
          <button class="carette-payment-btn">
            🔒 Payer ${amount} (SIMULÉ)
          </button>
        </div>
      </div>
    `;

    // Styles inline pour éviter les conflits
    const style = document.createElement('style');
    style.textContent = `
      .carette-payment-backdrop {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.7);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        animation: fadeIn 0.3s ease;
      }
      
      @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }
      
      .carette-payment-modal {
        background: white;
        border-radius: 16px;
        padding: 0;
        max-width: 500px;
        width: 90%;
        position: relative;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        animation: slideUp 0.3s ease;
      }
      
      @keyframes slideUp {
        from { transform: translateY(50px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
      }
      
      .carette-payment-close {
        position: absolute;
        top: 15px;
        right: 20px;
        font-size: 32px;
        font-weight: bold;
        color: white;
        cursor: pointer;
        z-index: 10;
        line-height: 1;
        transition: transform 0.2s;
      }
      
      .carette-payment-close:hover {
        transform: scale(1.1);
      }
      
      .carette-payment-content {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 40px 30px;
        border-radius: 16px;
        text-align: center;
      }
      
      .carette-payment-content h2 {
        margin: 0 0 20px 0;
        font-size: 28px;
        font-weight: 600;
      }
      
      .carette-payment-amount {
        font-size: 56px;
        font-weight: bold;
        margin: 20px 0;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
      }
      
      .carette-payment-content > p {
        margin: 0 0 30px 0;
        font-size: 16px;
        opacity: 0.95;
      }
      
      .carette-payment-notice {
        background: rgba(255, 255, 255, 0.15);
        backdrop-filter: blur(10px);
        padding: 20px;
        border-radius: 12px;
        margin: 20px 0 30px 0;
        font-size: 14px;
        line-height: 1.6;
        border: 1px solid rgba(255, 255, 255, 0.2);
      }
      
      .carette-payment-notice strong {
        font-size: 16px;
        display: block;
        margin-bottom: 8px;
      }
      
      .carette-payment-btn {
        background: white;
        color: #667eea;
        font-size: 18px;
        font-weight: bold;
        padding: 18px 40px;
        border: none;
        border-radius: 12px;
        cursor: pointer;
        transition: all 0.3s;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        font-family: inherit;
      }
      
      .carette-payment-btn:hover {
        transform: scale(1.05);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
      }
      
      .carette-payment-btn:active {
        transform: scale(0.98);
      }
      
      @media (max-width: 600px) {
        .carette-payment-modal {
          width: 95%;
          margin: 20px;
        }
        
        .carette-payment-amount {
          font-size: 42px;
        }
        
        .carette-payment-btn {
          font-size: 16px;
          padding: 15px 30px;
        }
      }
    `;
    
    document.head.appendChild(style);
    document.body.appendChild(this.backdrop);

    // Event listeners
    const closeBtn = this.backdrop.querySelector('.carette-payment-close');
    const payBtn = this.backdrop.querySelector('.carette-payment-btn');

    closeBtn.addEventListener('click', () => {
      this.close();
      onCancel();
    });

    this.backdrop.addEventListener('click', (e) => {
      if (e.target === this.backdrop) {
        this.close();
        onCancel();
      }
    });

    payBtn.addEventListener('click', () => {
      this.close();
      onConfirm();
    });

    // ESC pour fermer
    const handleEsc = (e) => {
      if (e.key === 'Escape') {
        this.close();
        onCancel();
        document.removeEventListener('keydown', handleEsc);
      }
    };
    document.addEventListener('keydown', handleEsc);
  }

  /**
   * Fermer la popup
   */
  close() {
    if (this.backdrop) {
      this.backdrop.remove();
      this.backdrop = null;
    }
  }
}

// Export pour utilisation dans le widget
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CarettePaymentSimulator;
}

// Instance globale
window.CarettePaymentSimulator = CarettePaymentSimulator;
