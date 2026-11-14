import Contacts
import UIKit

enum ContactBuilder {
    static func calypso(phone: String) -> CNMutableContact {
        let contact = CNMutableContact()
        contact.givenName = "Calypso⁻¹"
        contact.phoneNumbers = [
            CNLabeledValue(label: CNLabelPhoneNumberMobile, value: CNPhoneNumber(stringValue: phone)),
        ]
        contact.imageData = UIImage(named: "Logo")?.pngData()
        return contact
    }
}
