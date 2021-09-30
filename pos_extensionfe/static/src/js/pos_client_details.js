odoo.define('pos_extensionfe.pos_client_details', function(require) {

    const ClientDetailsEdit = require('point_of_sale.ClientDetailsEdit');
    const Registries = require('point_of_sale.Registries');

    const pos_ClientDetailsEdit = ClientDetailsEdit => class extends ClientDetailsEdit {
        constructor(){
				super(...arguments);
				this.intFields.push('x_country_county_id');
				this.intFields.push('x_country_district_id');
				this.intFields.push('x_identification_type_id');
			}

        saveChanges() {
            let processedChanges = {};
            for (let [key, value] of Object.entries(this.changes)) {
                if (this.intFields.includes(key)) {
                    processedChanges[key] = parseInt(value) || false;
                } else {
                    processedChanges[key] = value;
                }
            }

            if ((!this.props.partner.name && !processedChanges.name) ||
						processedChanges.name === '' ){
						return this.showPopup('ErrorPopup', {
							title: _('A Customer Name Is Required'),
						});
				}
            processedChanges.id = this.props.partner.id || false;
            this.trigger('save-changes', { processedChanges });
         }
    };

    Registries.Component.extend(ClientDetailsEdit, pos_ClientDetailsEdit);
    return ClientDetailsEdit;
});
