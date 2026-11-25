/**
 * tls_certs.h - TLS Certificate Storage for MQTT over TLS
 *
 * INSTRUCTIONS:
 * 1. Obtain the CA certificate from your MQTT broker.
 *    For Mosquitto self-signed: copy the content of ca.crt
 *    For HiveMQ Cloud: download from their dashboard
 *    For AWS IoT: download the Amazon Root CA 1
 *
 * 2. Replace the placeholder below with your actual PEM certificate.
 *
 * 3. The cert must be in PEM format (Base64, starts with -----BEGIN CERTIFICATE-----)
 *
 * 4. For SELF-SIGNED certs, also set:
 *       client.setInsecure();  // in main.ino (disables hostname verification)
 *    OR provide client cert + key for mutual TLS.
 */

#ifndef TLS_CERTS_H
#define TLS_CERTS_H

// Root CA Certificate for MQTT Broker TLS verification.
// Replace the content between the R"EOF( ... )EOF" with your cert.
const char ROOT_CA_CERT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
REPLACE_WITH_YOUR_MQTT_BROKER_CA_CERTIFICATE_IN_PEM_FORMAT
MIIDXTCCAkWgAwIBAgIJAK...
(paste full base64-encoded certificate here)
...xyz123==
-----END CERTIFICATE-----
)EOF";

// Optional: Client certificate for mutual TLS (mTLS)
// Leave empty strings if not using mTLS
const char CLIENT_CERT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
REPLACE_WITH_CLIENT_CERTIFICATE_IF_USING_MTLS
-----END CERTIFICATE-----
)EOF";

// Optional: Client private key for mutual TLS (mTLS)
// Leave empty strings if not using mTLS
const char CLIENT_KEY[] PROGMEM = R"EOF(
-----BEGIN RSA PRIVATE KEY-----
REPLACE_WITH_CLIENT_PRIVATE_KEY_IF_USING_MTLS
-----END RSA PRIVATE KEY-----
)EOF";

// HiveMQ Cloud root CA (pre-filled as example - use for HiveMQ Cloud free tier)
// Uncomment and use the ROOT_CA_HIVEMQ block if connecting to HiveMQ Cloud
/*
const char ROOT_CA_HIVEMQ[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
...
-----END CERTIFICATE-----
)EOF";
*/

#endif // TLS_CERTS_H
