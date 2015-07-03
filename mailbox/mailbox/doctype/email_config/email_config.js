$.extend(cur_frm.cscript, {
	onload: function(doc,cdt,cdn) {
		if (user && parseInt(doc.__islocal)!=0 && !doc.user){
			doc.user = user
		}
	}
});