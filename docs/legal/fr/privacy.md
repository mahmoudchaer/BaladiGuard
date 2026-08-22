> **Brouillon produit — pas une certification de conformité.** Ce document est un brouillon préparé pour l’examen du propriétaire de BaladiGuard et de son conseil juridique. Il ne constitue pas une certification de conformité au RGPD ni à tout autre cadre réglementaire.

# Politique de confidentialité

**Version :** 2026-08-22  
**Contact :** privacy@baladiguard.app  
**Âge prévu :** 16 ans et plus

## 1. Qui traite vos données

- **Opérateur de la plateforme BaladiGuard** — comptes citoyens, authentification OTP, sessions, journaux plateforme et opérations produit.
- **Municipalités participantes** — dossiers de tickets municipaux pour la réception, le routage, l’enquête et la résolution civique.

## 2. Ce que nous collectons

| Données | Finalité |
| --- | --- |
| Numéro de téléphone vérifié | Identité du compte, connexion (OTP), propriété des tickets, SMS si activés |
| Nom complet (facultatif) | Profil et attribution publique optionnelle lorsque vous l’activez |
| E-mail (facultatif) | Mises à jour / annonces uniquement si vous choisissez l’e-mail |
| Préférences de notification | Comment vous contacter au sujet de vos signalements |
| Enregistrement d’acceptation juridique | Preuve d’acceptation des Conditions, de la Politique de confidentialité et de l’Usage acceptable courants |
| Contenu du signalement | Description, lieu et photos nécessaires à l’enquête et à la résolution |
| Instantané de contact sur chaque ticket | Copie immuable à la soumission pour le suivi opérationnel |
| Sessions et défis OTP | Sécurité de connexion ; seuls des hachages cléés des codes OTP sont stockés |
| Métadonnées appareil / client à la soumission | Résistance aux abus et diagnostics de support (pas de marketing) |
| Messages WhatsApp (le cas échéant) | Prise en charge conversationnelle des signalements sur ce canal |
| Sorties de modération / IA | Revue de sécurité et classification assistée pour les flux civiques |
| Journaux opérationnels | Fiabilité, sécurité et support |

Nous ne vendons pas les données personnelles. Les comptes citoyens n’utilisent pas de mots de passe.

## 3. Bases et consentement

La création de compte et la connexion exigent l’acceptation du paquet juridique courant (`acceptLegal` lors de la vérification OTP). Les points de profil et de réacceptation enregistrent la même version. Le traitement municipal des tickets soutient le service civique selon les politiques des municipalités participantes.

## 4. Conservation (résumé)

Le détail de référence figure dans `docs/data-inventory.md` et `docs/privacy-lifecycle.md`. En bref :

- Comptes citoyens actifs : tant que le compte reste actif
- Tombstones anonymisés : conservés pour l’intégrité propriété/audit, PII effacée
- Tickets municipaux et instantanés de contact : conservés pour les opérations municipales
- Sessions citoyennes : TTL absolu d’environ 30 jours
- Défis OTP : TTL d’environ 5 minutes
- Journaux applicatifs : généralement 30–90 jours

## 5. Vos contrôles

- Consulter et mettre à jour le profil
- Exporter le compte et les résumés de tickets détenus
- Supprimer / anonymiser le compte
- Réaccepter les textes juridiques mis à jour
- Contrôler la visibilité publique du nom (désactivée par défaut)

## 6. Partage

Les données sont partagées avec les municipalités participantes autant que nécessaire pour traiter les signalements, et avec des sous-traitants d’infrastructure (hébergement, SMS/e-mail, stockage d’objets) selon des contrats opérationnels. Nous ne vendons pas les données personnelles.

## 7. Notes internationales et de sécurité

Les données peuvent être traitées dans les régions cloud configurées pour le déploiement. Nous appliquons des contrôles d’accès, la révocation de sessions et le moindre privilège pour le personnel. Aucun service en ligne ne peut garantir une sécurité absolue.

## 8. Mineurs

Le Service est destiné aux utilisateurs de 16 ans et plus. N’utilisez pas le Service si vous êtes plus jeune.

## 9. Contact et demandes

privacy@baladiguard.app

Les demandes de confidentialité peuvent aussi être traitées via l’export/suppression en libre-service ou la voie manuelle documentée dans `docs/privacy-lifecycle.md`.
