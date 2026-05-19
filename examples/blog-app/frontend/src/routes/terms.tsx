import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/terms')({
  component: TermsPage,
});

function TermsPage() {
  return (
    <div className="container mx-auto max-w-4xl px-4 py-12">
      <div className="prose prose-gray dark:prose-invert max-w-none">
        <h1 className="text-3xl font-bold tracking-tight">Terms of Service</h1>
        <p className="text-lg text-muted-foreground">
          Last updated: {new Date().toLocaleDateString()}
        </p>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Acceptance of Terms</h2>
          <p>
            By accessing and using this service, you accept and agree to be
            bound by the terms and provision of this agreement. If you do not
            agree to abide by the above, please do not use this service.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Description of Service</h2>
          <p>
            Our service provides a platform for task management and productivity
            tools. We reserve the right to modify, suspend, or discontinue the
            service at any time without notice.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">User Accounts</h2>
          <p>
            To access certain features of the service, you must register for an
            account. You are responsible for:
          </p>
          <ul>
            <li>Maintaining the confidentiality of your account credentials</li>
            <li>All activities that occur under your account</li>
            <li>Providing accurate and complete information</li>
            <li>Updating your information as necessary</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Acceptable Use</h2>
          <p>You agree not to use the service to:</p>
          <ul>
            <li>Violate any applicable laws or regulations</li>
            <li>Infringe on the rights of others</li>
            <li>Upload malicious code or content</li>
            <li>Attempt to gain unauthorized access to our systems</li>
            <li>Interfere with the proper functioning of the service</li>
            <li>Use the service for commercial purposes without permission</li>
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">
            Content and Intellectual Property
          </h2>
          <p>
            You retain ownership of content you create using our service.
            However, by using the service, you grant us a license to use,
            modify, and display your content as necessary to provide the
            service.
          </p>
          <p>
            All service-related intellectual property, including but not limited
            to software, design, and trademarks, remains our property.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Privacy</h2>
          <p>
            Your privacy is important to us. Please review our Privacy Policy,
            which also governs your use of the service, to understand our
            practices.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Disclaimers</h2>
          <p>
            The service is provided "as is" without any warranties, express or
            implied. We do not guarantee that the service will be uninterrupted,
            secure, or error-free.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Limitation of Liability</h2>
          <p>
            In no event shall we be liable for any indirect, incidental,
            special, consequential, or punitive damages, including without
            limitation, loss of profits, data, use, goodwill, or other
            intangible losses.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Termination</h2>
          <p>
            We may terminate or suspend your account and access to the service
            immediately, without prior notice, for any reason, including
            violation of these terms.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Changes to Terms</h2>
          <p>
            We reserve the right to modify these terms at any time. We will
            notify users of any changes by posting the new terms on this page
            and updating the "Last updated" date.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold">Contact Information</h2>
          <p>
            If you have any questions about these terms, please contact us at:
          </p>
          <ul>
            <li>Email: legal@example.com</li>
            <li>Address: [Your Company Address]</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
