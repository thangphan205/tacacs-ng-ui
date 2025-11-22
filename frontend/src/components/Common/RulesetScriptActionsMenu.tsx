import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { RulesetScriptPublic } from "@/client"
import DeleteRulesetScript from "../RulesetScripts/DeleteRulesetScript"
import EditRulesetScript from "../RulesetScripts/EditRulesetScript"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface RulesetScriptActionsMenuProps {
  rulesetscript: RulesetScriptPublic
}

export const RulesetScriptActionsMenu = ({ rulesetscript }: RulesetScriptActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditRulesetScript rulesetscript={rulesetscript} />
        <DeleteRulesetScript rulesetscript={rulesetscript} />
      </MenuContent>
    </MenuRoot>
  )
}
